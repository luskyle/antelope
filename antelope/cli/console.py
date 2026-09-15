from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText

class Console():
    def WriteNotice(self, msg:str):
        text = FormattedText([
            ('#0483b1', msg),
        ])
        print_formatted_text(text)
