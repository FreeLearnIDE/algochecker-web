import json
import yaml

from django.core.exceptions import ValidationError

from zipfile import ZipFile, BadZipFile


def validate_package(package):
    try:
        with ZipFile(package, 'r') as package_zip:
            file_names = package_zip.namelist()
            accepted_conf_files = {'config.json', 'config.yml'}
            conf_file_names = accepted_conf_files.intersection(file_names)
            if not conf_file_names:
                raise ValidationError('Package does not contain any of the following: %s.'
                                      % ', '.join(accepted_conf_files))
            elif len(conf_file_names) > 1:
                raise ValidationError('There must be only one config file.')

            file_name = conf_file_names.pop()
            ext = file_name.split('.')[-1]
            with package_zip.open(file_name) as conf_file:
                # when we support more config types, we should think about more abstract approach to validating them
                if ext == 'json':
                    try:
                        json.loads(conf_file.read().decode())
                    except json.JSONDecodeError as er:
                        raise ValidationError('Invalid JSON file: %s' % str(er))
                elif ext == 'yml':
                    try:
                        yaml.safe_load(conf_file)
                    except yaml.MarkedYAMLError as er:
                        raise ValidationError('Invalid YAML file: %s' % str(er))
    except BadZipFile:
        raise ValidationError('Provided package is not a valid .zip file')
    except RuntimeError as e:
        raise ValidationError('Invalid package: %s' % str(e.args[0]))
