from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound


class ListHtmlFormatter(HtmlFormatter):
    def wrap(self, source, outfile):
        return self._wrap_div(
            self._wrap_pre(
                    self._wrap_lines(source)
            )
        )

    @staticmethod
    def _wrap_lines(source):
        ln = ''
        lc = ''
        n = 0

        for i, line in source:
            if i == 1:
                n += 1
                f = ' first' if n == 1 else ''
                ln += '<div class="l-num{}" data-n="{}">{}</div>'.format(f, n, n)
                lc += '<div class="l-code{}" data-n="{}">{}</div>'.format(f, n, line)

        yield 0, '<table><tr><td class="lines-gutter">{}</td><td class="code-content">{}</td></tr></table>'.format(ln,
                                                                                                                   lc)


def highlight_submission_files(files):
    """
    Gets the list of SubmissionFile objects and returns
    id-indexed dictionary of their HTML formatted highlights
    """
    formatter = ListHtmlFormatter()
    out = {}

    for fl in files:
        try:
            contents = fl.contents.read().decode('utf-8', 'replace')
            lexer = get_lexer_for_filename(fl.name)
        except (UnicodeDecodeError, ClassNotFound):
            out[fl.id] = None
        else:
            out[fl.id] = {
                "lang": lexer.name,
                "html": highlight(contents, lexer, formatter)
            }

    return out
