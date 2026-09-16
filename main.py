import os
import logging
import threading
import requests
from flask import Flask
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))
user_set = set()

# Dummy Flask app to satisfy Render's Web Service port requirements
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "FOGER Bot is live and running!"

def run_flask():
    app_flask.run(host='0.0.0.0', port=PORT)

# External API helper for TikTok to prevent Render IP bans
def fetch_tiktok_data(url):
    try:
        api_url = f"https://api.tiklydown.eu.org/api/download?url={url}"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logging.error(f"TikTok API Exception: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    welcome_text = (
        f"🤖 **FOGER Downloader Bot**\n"
        f"👥 *Active Users:* `{len(user_set)} users`\n\n"
        f"Send me any video or photo link from TikTok, Facebook, Instagram, or YouTube!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    status_msg = await update.message.reply_text("🔄 Processing your link... Please wait!")

    # 1. Dedicated TikTok Logic (Photo Slideshows & Videos)
    if "tiktok.com" in url or "vm.tiktok.com" in url or "vt.tiktok.com" in url:
        data = fetch_tiktok_data(url)
        
        if data:
            images = data.get("images", [])
            if images:
                await status_msg.edit_text("📸 Downloading photo album...")
                media_group = [
                    InputMediaPhoto(
                        media=img_url, 
                        caption="Downloaded via @FOGER_downloader_bot" if i == 0 else ""
                    ) for i, img_url in enumerate(images[:10])
                ]
                await update.message.reply_media_group(media=media_group)
                await status_msg.delete()
                return

            video_url = data.get("video", {}).get("noWatermark") or data.get("video", {}).get("watermark")
            if video_url:
                await status_msg.edit_text("📤 Uploading video...")
                await update.message.reply_video(
                    video=video_url,
                    caption="Downloaded via @FOGER_downloader_bot"
                )
                await status_msg.delete()
                return

    # 2. General Downloader (YouTube, Facebook, Instagram)
    ydl_opts = {
        'format': 'bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                
                if file_size_mb > 49.5:
                    await status_msg.edit_text("⚠️ Video size exceeds Telegram's 50MB limit.")
                    os.remove(file_path)
                    return

                await status_msg.edit_text("📤 Uploading video...")
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="Downloaded via @FOGER_downloader_bot"
                    )
                
                os.remove(file_path)
                await status_msg.delete()

    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
        await status_msg.edit_text("❌ Failed to download media. Please check if the link is public or valid.")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Start Flask Web Server in a background thread to keep Render alive
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))

    print("Bot service initialized...")
    app.run_polling()

if __name__ == '__main__':
    main()
