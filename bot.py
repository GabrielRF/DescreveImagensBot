import base64
import bot_config
import telebot
import os
from openai import OpenAI

TOKEN = bot_config.TOKEN
OPENAI_KEY = bot_config.OPENAI_KEY
CHATIDS = bot_config.CHATIDS

INPUT_PRICE = bot_config.INPUT_PRICE
OUTPUT_PRICE = bot_config.OUTPUT_PRICE

bot = telebot.TeleBot(TOKEN)

def moderate_content(image):
    client = OpenAI(api_key=OPENAI_KEY)
    reason = None

    input=[
        {'type': 'image_url', 'image_url': {'url': image} }
    ]

    response = client.moderations.create(
        model='omni-moderation-latest',
        input = input
    )

    if response.results[0].flagged:
        for category in response.results[0].category_scores:
            if category[1] > 0.5:
                reason = f'{category[0]} {category[1]:.2f}\n'

    return reason

def download_photo(message):
    photo_info = bot.get_file(message.photo[-1].file_id)
    photo_download = bot.download_file(photo_info.file_path)
    photo_name = f'{photo_info.file_unique_id[:6]}.{photo_info.file_path.split(".")[-1]}'
    with open(photo_name, 'wb') as new_photo:
        new_photo.write(photo_download)
    return photo_name

def encode_image(photo_name):
  with open(photo_name, "rb") as photo_file:
    return base64.b64encode(photo_file.read()).decode('utf-8')

def describe_photo(photo_encoded):
    client = OpenAI(api_key=OPENAI_KEY)

    input=[
        {'role': 'user', 'content':
            [
                {'type': 'input_text', 'text': 'Descreva a imagem'},
                {
                    'type': 'input_image',
                    'image_url': f'data:image/jpeg;base64,{photo_encoded}',
                    'detail': 'high'
                }
            ]
        }
    ]

    response = client.responses.create(
        model='gpt-4o-mini',
        input=input
    )

    description = response.output_text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    input_price = input_tokens * (INPUT_PRICE/1000000)
    output_price = input_tokens * (OUTPUT_PRICE/1000000)
    total_cost = input_price + output_price
    return description, total_cost

def react_to_message(chatid, messageid, emoji):
    if emoji:
        emoji=[telebot.types.ReactionTypeEmoji(f'{emoji}')]
    try:
        telebot.util.antiflood(
            bot.set_message_reaction(
                chatid,
                messageid,
                emoji
            )
        )
    except:
        pass

def remove_photo(photo_name):
    os.remove(photo_name)

def send_result(message, text):
    telebot.util.antiflood(
        bot.send_message,
        message.chat.id,
        text,
        parse_mode='HTML',
        reply_to_message_id=message.id
    )

@bot.message_handler(commands=["start"])
def cmd_start(message):
    telebot.util.antiflood(
        bot.send_chat_action,
        message.chat.id,
        'typing'
    )
    message_text = (
        f'👋 <b>Olá, {telebot.formatting.escape_html(message.from_user.first_name)}</b>,'
        '\n\n🖼 Sou responsável por descrever imagens enviadas a mim ou a grupos que faço parte.'
        '\n\n🧠 Utilizo a interligência artificial da OpenAI para gerar as descrições.'
        #'\n\n⚙️ Possuo código aberto, disponível em: https://github.com/GabrielRF/DescreveImagensBot'
        '\n\n🆘 Contato com o desenvolvedor: https://chat.grf.xyz/DescreveImagensBot'
    )
    telebot.util.antiflood(
        bot.send_message,
        message.chat.id,
        message_text,
        parse_mode='HTML',
        link_preview_options=telebot.types.LinkPreviewOptions(is_disabled=True)
    )

@bot.message_handler(chat_types=['group', 'supergroup', 'private'], content_types=['photo'])
@bot.edited_message_handler(chat_types=['group', 'supergroup', 'private'], content_types=['photo'])
def describe_image_handler(message):
    if message.chat.id not in CHATIDS:
        bot.reply_to(message, "<b>Acesso negado</b>\nBot em alpha privado.", parse_mode='HTML')
        return
    react_to_message(message.chat.id, message.message_id, '👀')
    photo_url = (
        f'https://api.telegram.org/file/bot{TOKEN}/' +
        f'{bot.get_file(message.photo[-1].file_id).file_path}'
    )
    moderated = moderate_content(photo_url)
    if not moderated:
        photo_name = download_photo(message)
        photo_encoded = encode_image(photo_name)
        description, total_cost = describe_photo(photo_encoded)
        text = (
            f'🖼  <b>Descrição automática:</b>'
            f'\n<blockquote expandable>{description}</blockquote>'
            f'\n💳 <span class="tg-spoiler">Custo: US$ {total_cost:.4f}</span>'
        )
        remove_photo(photo_name)
    else:
        text = (
            f'⚠️ <b>Imagem ignorada</b>!'
            f'\n\n<b>📋 Motivos</b>:'
            f'\n<code>{moderated}</code>'
        )
    send_result(message, text)
    react_to_message(message.chat.id, message.message_id, None)

if __name__ == "__main__":
    bot.infinity_polling()
