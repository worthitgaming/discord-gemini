import json
import time
import os
import random
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

discord_token = os.getenv('DISCORD_TOKEN')
google_api_key = os.getenv('GOOGLE_API_KEY')

last_message_id = None
bot_user_id = None
last_ai_response = None

def log_message(message):
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}")

def generate_reply(prompt, use_google_ai=True, use_file_reply=False, language="id"):
    global last_ai_response

    if use_file_reply:
        log_message("💬 Menggunakan pesan dari file sebagai balasan.")
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

    if use_google_ai:
        if language == "en":
            ai_prompt = (
                f"{prompt}\n\n"
                "Reply with casual tone, max 10–12 words. "
                "Use natural, chill English without emojis or symbols."
            )
        else:
            ai_prompt = (
                f"{prompt}\n\n"
                "Balas dengan gaya santai, kayak ngobrol biasa. "
                "Maksimal 10-12 kata, bahasa gaul Jakarta. "
                "Tanpa simbol, emoji, atau tanda baca aneh. "
                "Jangan terlalu formal. Anggap kayak chat ke temen."
            )

        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                ai_response = response.json()
                response_text = ai_response['candidates'][0]['content']['parts'][0]['text']

                if response_text == last_ai_response:
                    log_message("⚠️ AI memberikan balasan yang sama, mencoba ulang...")
                    continue

                last_ai_response = response_text
                return ai_response

            except requests.exceptions.RequestException as e:
                log_message(f"⚠️ Request failed: {e}")
                return None

        log_message("⚠️ AI terus memberikan balasan yang sama, menggunakan respons terakhir.")
        return {"candidates": [{"content": {"parts": [{"text": last_ai_response or 'Maaf, tidak dapat membalas pesan.'}]}}]}
    else:
        return {"candidates": [{"content": {"parts": [{"text": get_random_message()}]}}]}

def get_random_message():
    try:
        with open('pesan.txt', 'r') as file:
            lines = file.readlines()
            if lines:
                return random.choice(lines).strip()
            else:
                log_message("File pesan.txt kosong.")
                return "Tidak ada pesan yang tersedia."
    except FileNotFoundError:
        log_message("File pesan.txt tidak ditemukan.")
        return "File pesan.txt tidak ditemukan."

def send_message(channel_id, message_text, reply_to=None, reply_mode=True):
    headers = {
        'Authorization': f'{discord_token}',
        'Content-Type': 'application/json'
    }

    payload = {'content': message_text}

    if reply_mode and reply_to:
        payload['message_reference'] = {'message_id': reply_to}

    try:
        response = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", json=payload, headers=headers)
        response.raise_for_status()

        if response.status_code in [200, 201]:
            data = response.json()
            log_message(f"✅ Sent message (ID: {data.get('id')}): {message_text}")
        else:
            log_message(f"⚠️ Failed to send message: {response.status_code}")
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Request error: {e}")

def auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language, reply_mode):
    global last_message_id, bot_user_id

    headers = {'Authorization': f'{discord_token}'}

    try:
        bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
        bot_info_response.raise_for_status()
        bot_user_id = bot_info_response.json().get('id')
    except requests.exceptions.RequestException as e:
        log_message(f"⚠️ Failed to retrieve bot information: {e}")
        return

    while True:
        try:
            response = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
            response.raise_for_status()

            if response.status_code == 200:
                messages = response.json()
                if len(messages) > 0:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')

                    if (last_message_id is None or int(message_id) > int(last_message_id)) and author_id != bot_user_id and message_type != 8:
                        user_message = most_recent_message.get('content', '')
                        log_message(f"💬 Received message: {user_message}")

                        result = generate_reply(user_message, use_google_ai, use_file_reply, language)
                        response_text = result['candidates'][0]['content']['parts'][0]['text'] if result else "Maaf, tidak dapat membalas pesan."

                        log_message(f"⏳ Waiting {reply_delay} seconds before replying...")
                        time.sleep(reply_delay)

                        if reply_mode == 'random':
                            is_reply = random.choice([True, False])
                        else:
                            is_reply = reply_mode == 'reply'

                        send_message(channel_id, response_text, reply_to=message_id if is_reply else None, reply_mode=is_reply)
                        last_message_id = message_id

            log_message(f"⏳ Waiting {read_delay} seconds before checking for new messages...")
            time.sleep(read_delay)
        except requests.exceptions.RequestException as e:
            log_message(f"⚠️ Request error: {e}")
            time.sleep(read_delay)

if __name__ == "__main__":
    use_reply = input("Ingin menggunakan fitur auto-reply? (y/n): ").lower() == 'y'
    channel_id = input("Masukkan ID channel: ")

    if use_reply:
        use_google_ai = input("Gunakan Google Gemini AI untuk balasan? (y/n): ").lower() == 'y'
        use_file_reply = input("Gunakan pesan dari file pesan.txt? (y/n): ").lower() == 'y'
        reply_mode_input = input("Ingin membalas pesan (reply/send/random): ").lower()

        if reply_mode_input not in ["reply", "send", "random"]:
            log_message("⚠️ Mode tidak valid, default ke 'reply'.")
            reply_mode_input = "reply"

        language_choice = input("Pilih bahasa untuk balasan (id/en): ").lower()
        if language_choice not in ["id", "en"]:
            log_message("⚠️ Bahasa tidak valid, default ke bahasa Indonesia.")
            language_choice = "id"

        read_delay = int(input("Set Delay Membaca Pesan Terbaru (dalam detik): "))
        reply_delay = int(input("Set Delay Balas Pesan (dalam detik): "))

        log_message(f"✅ Mode balasan aktif ({reply_mode_input}) dalam bahasa {'Indonesia' if language_choice == 'id' else 'Inggris'}...")
        auto_reply(channel_id, read_delay, reply_delay, use_google_ai, use_file_reply, language_choice, reply_mode_input)

    else:
        send_interval = int(input("Set Interval Pengiriman Pesan (dalam detik): "))
        log_message("✅ Mode kirim pesan acak aktif...")

        while True:
            message_text = get_random_message()
            send_message(channel_id, message_text, reply_mode=False)
            log_message(f"⏳ Waiting {send_interval} seconds before sending the next message...")
            time.sleep(send_interval)
