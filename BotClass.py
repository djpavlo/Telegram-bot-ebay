import Utils
from Utils import error_handler, restart_handler
from Utils import Bunch
from Utils import generate_markup
import Settings
from EbayApiHelper import EbayApiHelper
from ResponseParser import ResponseParser
import random
from telebot import types
from xml.dom import minidom


class Bot:
    request_dict = {}
    bot = Utils.bot

    # Main commands

    # !
    @error_handler
    @bot.message_handler(commands=['start'])
    def start(message):
        Bot.bot.send_message(message.chat.id, reply_markup=Settings.markup_home,
                             text="Hello \U0001f604")

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Get progress")
    def send_progress(call):
        """Send progress to user"""

        request = Bot.request_dict[call.message.chat.id]
        Bot.bot.send_message(call.message.chat.id, request.progress)

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data in Settings.CHANGES)
    def process_next_changes(call):
        """What bot should to do after changing settings"""

        chat_id = call.message.chat.id
        request = Bot.request_dict[chat_id]
        request.change = False
        if call.data == 'Change another one setting':
            Utils.functions[call.data](call)
        elif call.data == 'Get results':
            if request.keywords:
                Bot.send_results(call.message, request)
            else:
                Utils.functions["Search"](call)
                Bot.bot.register_next_step_handler(call.message, Bot.process_changes_fin)
        else:
            request.change = False

    # Handlers for main keyboard's buttons
    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Main Menu")
    def load_main_menu(call):
        """Go back to the home page from search"""

        Bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  reply_markup=Settings.markup_home,
                                  text="Hello")

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Settings")
    def process_settings(call):
        """Permit user to change some parameters of request"""

        Bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  reply_markup=generate_markup(Settings.SETTINGS),
                                  text="Tap on the setting you'd like to change")

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Search")
    def process_search(call):
        Utils.functions["Search"](call)
        Bot.bot.register_next_step_handler(call.message, Bot.process_keywords)

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Result")
    def process_result(call):
        pass

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data == "Help")
    def process_help(call):
        pass

    # Create new request
    @error_handler
    @restart_handler
    def process_keywords(message):
        chat_id = message.chat.id
        request = Bunch(keywords=None, sort=None, feedback=None,
                        rating=None, progress=0, change=None,  markups={"rating": Settings.RATING,
                                                                        "num": Settings.NUM_KEYBOARD})
        Bot.request_dict[chat_id] = request
        request.keywords = message.text
        Bot.bot.reply_to(message, reply_markup=generate_markup(Settings.SORT_ORDERS),
                         text="Please, choose the sort order")

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data in Settings.SORT_ORDERS)
    def process_sellers_sort(call):
        request = Bot.request_dict[call.message.chat.id]
        request.sellers = call.message.text
        markup = Settings.RATING
        Bot.changes_detector(call, request, "How high should be seller's rating? ", markup)

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data[:6] == 'rating')
    def process_sellers_rating(call):
        request = Bot.request_dict[call.message.chat.id]
        if "keyboard" in call.data:
            Utils.change_num_keyword(request, 'rating', call)
        else:
            request.rating = call.data[7:]
            markup = types.InlineKeyboardMarkup()
            buttons = []
            for i in [100, 1000, 10000, None]:
                buttons.append(types.InlineKeyboardButton(text=str(i), callback_data="feedback" + str(i)))
            markup.row(*buttons)
            markup.row(*Settings.last_row)
            Bot.changes_detector(call, request, "How high should be number of seller's feedback?", markup)

    @error_handler
    @bot.callback_query_handler(func=lambda call: call.data[:8] == 'feedback')
    def process_sellers_rating(call):
        chat_id = call.message.chat.id
        request = Bot.request_dict[chat_id]
        request.feedback = call.data[8:]
        markup = Settings.NUM_KEYBOARD
        if not request.change:
            Bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      reply_markup=markup,
                                      text="How many items do you want to see?")
        Bot.bot.register_next_step_handler(call.message, Bot.process_num)

    @error_handler
    @restart_handler
    @bot.callback_query_handler(func=lambda call: call.data[:3] == 'num')
    def process_num(call):
        request = Bot.request_dict[call.message.chat.id]
        if "keyboard" in call.data:
            Utils.change_num_keyword(request, 'num', call)
        else:
            request.num = int(call.data[3:])
            Bot.send_results(call.message, request)

    @error_handler
    @restart_handler
    def process_changes_fin(message):
        request = Bot.request_dict[message.chat.id]
        request.keywords = message.text
        Bot.send_results(message, request)

    @error_handler
    @restart_handler
    def send_results(message, request):
        Bot.bot.edit_message_text(chat_id=message.chat.id, message_id=message.message_id,
                                  reply_markup=Settings.progress_button,
                                  text="Please, wait...")
        request.progress = 0
        helper = EbayApiHelper(request.keywords, request)
        futures = helper.futures(Settings.PAGES)
        xmldocs = []
        for i in futures:
            xmldocs.append(minidom.parse(i.result()))
        parser = ResponseParser(xmldocs, request.sellers, request.rating, request.feedback)
        result = parser.parse_request()
        items = result
        for item in items[:request.num]:
            Bot.bot.send_message(message.chat.id, item)
        Bot.bot.send_message(message.chat.id, reply_markup=Settings.markup_home,
                             text="Hello \U0001f604")

    @error_handler
    @bot.callback_query_handler(func=lambda call: True)
    def process_change_settings(call):
        """Get the name of parameter user'd like to change"""

        chat_id = call.message.chat.id
        request = Bot.request_dict.get(chat_id)
        if not request:
            request = Bunch(keywords=None, sort=None,
                            solds=None, rating=None, progress=0,
                            change=None, num=Settings.NUM)
            Bot.request_dict[chat_id] = request
        change = call.data
        request.change = True
        Bot.bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  reply_markup=generate_markup(Settings.MARKUPS[change]),
                                  text="Change setting")

    @classmethod
    def changes_detector(cls, call, request, text, markup):
        if not request.change:
            cls.bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      reply_markup=markup,
                                      text=text)
        else:
            cls.bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      reply_markup=generate_markup(Settings.CHANGES),
                                      text="What do you want to do?")


if __name__ == '__main__':
    random.seed()
    Bot = Bot()
    Bot.bot.remove_webhook()
    Bot.bot.polling(none_stop=True)