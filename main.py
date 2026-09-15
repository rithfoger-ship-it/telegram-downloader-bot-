import os
import logging
import threading
from flask import Flask
import yt_dlp
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Flask Keep-Alive Server for Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is active and running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8202844679:AAHFXd_R7jfnbm7L63qtnJB31pbaEsh4Ubo"
MAX_FILE_SIZE = 50 * 1024 * 1024

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Send me a link from YouTube, TikTok, Facebook, or Instagram to download.\n\n"
        "• Send Link = Download Video or Photo Slide\n"
        "• /audio <link> = Download MP3 Audio"
    )

async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return

    status_message = await update.message.reply_text("⏳ Processing link, please wait...")

    # Extract metadata first to check if it is a photo slideshow
    ydl_opts_info = {
        'quiet': True,
        'http_headers': HEADERS,
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)

        # Handle TikTok / Instagram Photo Slideshows
        if info.get('entries') or (info.get('images') and len(info.get('images')) > 0):
            await status_message.edit_text("📸 Extracting images from slideshow...")
            images = info.get('images', [])
            media_group = []

            for idx, img_url in enumerate(images[:10]):  # Limit to max 10 photos per batch
                media_group.append(InputMediaPhoto(media=img_url))

            if media_group:
                await update.message.reply_media_group(media=media_group)
                await status_message.delete()
                return

        # Handle Video Downloads (Auto-compress format under 50MB)
        await status_message.edit_text("⏳ Downloading video (optimizing size under 50MB)...")
        output_file = f"video_{update.message.message_id}.mp4"

        ydl_opts_video = {
            'format': 'best[filesize<50M]/bestvideo[filesize<25M]+bestaudio/best',
            'outtmpl': output_file,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'http_headers': HEADERS,
            'nocheckcertificate': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([url])

        if not os.path.exists(output_file):
            raise Exception("File creation failed")

        file_size = os.path.getsize(output_file)
        if file_size > MAX_FILE_SIZE:
            mb_size = round(file_size / (1024 * 1024), 2)
            await status_message.edit_text(f"❌ Video is too large ({mb_size}MB). Telegram API limit is 50MB.")
            os.remove(output_file)
            return

        await status_message.edit_text("📤 Uploading video...")

        with open(output_file, 'rb') as video:
            await update.message.reply_video(video=video, caption="Downloaded successfully! ✅")

        if os.path.exists(output_file):
            os.remove(output_file)
        await status_message.delete()

    except Exception as e:
        print(f"Error: {e}")
        await status_message.edit_text("❌ Failed to download media. Please check the link or try another one.")
        if 'output_file' in locals() and os.path.exists(output_file):
            os.remove(output_file)

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage format: /audio <link>")
        return

    url = context.args[0].strip()
    status_message = await update.message.reply_text("⏳ Downloading audio...")
    output_file = f"audio_{update.message.message_id}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_file,
        'quiet': True,
        'socket_timeout': 30,
        'http_headers': HEADERS,
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_file):
            raise Exception("File creation failed")

        file_size = os.path.getsize(output_file)
        if file_size > MAX_FILE_SIZE:
            mb_size = round(file_size / (1024 * 1024), 2)
            await status_message.edit_text(f"❌ File too large ({mb_size}MB). Telegram limit is 50MB.")
            os.remove(output_file)
            return

        await status_message.edit_text("📤 Uploading audio...")

        with open(output_file, 'rb') as audio:
            await update.message.reply_audio(audio=audio, caption="Audio downloaded successfully! 🎵")

        if os.path.exists(output_file):
            os.remove(output_file)
        await status_message.delete()

    except Exception as e:
        print(f"Error: {e}")
        await status_message.edit_text("❌ Failed to download audio.")
        if os.path.exists(output_file):
            os.remove(output_file)

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("audio", download_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_media))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()