from django.db import transaction

import algoweb.settings
import logging
import redis
import json

from django.core.management import BaseCommand

from time import sleep

from webapp.models import SubmissionEvaluation, SubmissionTest, Submission


class Command(BaseCommand):
    help = "Starts the Redis poller which is an essential background task for webapp"

    @staticmethod
    def pick_indices(dictionary, indices):
        return {k: v for (k, v) in dictionary.items() if k in indices}

    def create_evaluation(self, data_text):
        try:
            data = json.loads(data_text.decode('utf-8'))
        except UnicodeDecodeError:
            logging.error('Unable to decode the data')
            return False

        try:
            submission = Submission.objects.get(pk=data['uuid'])
        except (ValueError, Submission.DoesNotExist):
            logging.error("Refusing to store evaluation with invalid or nonexistent UUID: {}".format(data['uuid']))
            return False

        if SubmissionEvaluation.objects.filter(submission__pk=data['uuid']).exists():
            logging.error("Refusing to store evaluation for already evaluated task, UUID: {}".format(data['uuid']))
            return False

        eval_args = self.pick_indices(data, ['message', 'result', 'score', 'status'])
        try:
            if data['time_stats']:
                eval_args['worker_start_time'] = data['time_stats']['finished_ms']
                eval_args['worker_end_time'] = data['time_stats']['started_ms']
                eval_args['worker_took_time'] = data['time_stats']['took_time_ms']
        except KeyError:
            pass

        with transaction.atomic():
            evaluation = SubmissionEvaluation(submission=submission, is_invalid=False, **eval_args)
            evaluation.save()

            test_outputs = self.get_test_outputs(data['uuid'])

            for test_obj in data['tests']:
                test_args = self.pick_indices(test_obj, ['name', 'status', 'time', 'memory', 'points', 'max_points'])

                if 'points' not in test_args or test_args['points'] is None:
                    test_args['points'] = 0

                if 'max_points' not in test_args or test_args['max_points'] is None:
                    test_args['max_points'] = 0

                try:
                    test_output = test_outputs[test_args['name']]
                    test_args['output'] = test_output['test_output']
                    test_args['output_visibility'] = test_output['test_output_visibility']
                except KeyError:
                    logging.info("There is no output to store for test '{}'".format(test_args['name']))

                test = SubmissionTest(evaluation=evaluation, **test_args)
                test.save()

        logging.info("Saved evaluation for UUID: {}".format(data['uuid']))
        return True

    @staticmethod
    def get_test_outputs(submission_uuid):
        rs = redis.Redis(**algoweb.settings.REDIS_CONFIG)
        result = rs.hgetall("evaluation:{}".format(submission_uuid))
        test_outputs = {}
        try:
            for k, v in result.items():
                k = k.decode('utf-8').split(':')
                v = v.decode('utf-8')
                if k[0] in ['test_output', 'test_output_visibility']:
                    try:
                        test_outputs[k[1]][k[0]] = v
                    except KeyError:
                        # in this case we don't have test_outputs[k[1]] initialized
                        test_outputs[k[1]] = {}
                        test_outputs[k[1]][k[0]] = v
        except (KeyError, UnicodeDecodeError):
            logging.exception("Cannot store the output")

        return test_outputs

    def handle(self, *args, **options):
        log_format = '[%(asctime)s][%(levelname)s] %(message)s'
        log_datefmt = '%d/%m/%Y %H:%M:%S'
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt=log_datefmt)

        logging.info('Connecting to Redis...')
        rs = redis.Redis(**algoweb.settings.REDIS_CONFIG)
        rsp = rs.pubsub()

        while True:
            try:
                rsp.subscribe('reports')
                for item in rsp.listen():
                    if item['type'] == 'message':
                        self.create_evaluation(item['data'])
                    elif item['type'] == 'subscribe' and item['data'] == 1:
                        logging.info("Successfully subscribed to: {}.".format(item['channel'].decode('utf-8')))
                        logging.info("Ready to accept submission evaluations.")
                    else:
                        logging.error("Unknown message: {}".format(item))
            except redis.exceptions.ConnectionError:
                logging.error("Redis connection failed, retrying in 5 seconds...")
                sleep(5)
