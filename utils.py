import config
import telebot
import functools

bot = telebot.TeleBot(config.token)


def error_handler(func):
    """Handle errors and fix issue with multiple dialogs"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            #Check if args start with '__main__.Bot' or message
            index = 0
            try:
                message = args[0]
                text = message.text
            except:
                index = 1
                message = args[1]
                text = message.text

            # do nothing because another one bot will handle '/start'
            if (text == '/start'):
                return

            return func(*args[index:], **kwargs)
        except Exception as e:
            raise e
    return wrapper

def input_validation(func):
    """Checks if the message.text isdigit or not"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print('in')
        print(*args)
        message = args[0]
        num = message.text
        if not num.isdigit():
            message = bot.reply_to(message,
                                       text="Please, enter a number")
            bot.register_next_step_handler(message, error_handler(input_validation(func)))
            return
        return func(*args, **kwargs)
    return wrapper