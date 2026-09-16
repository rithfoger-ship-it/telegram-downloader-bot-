import os
import logging
import asyncio
import json
import urllib.request
from aiohttp import web
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

# TikTok API Fetcher
def fetch_tiktok_data(url):
    try:
        api_url = f"https://api.tiklydown.eu.org/api/download?url={url}"
        req = urllib.request.Request(
            api_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                return json.loads(data)
    except Exception as e:
        logging.error(f"TikTok API Exception: {e}")
    return None

# Async wrapper for yt-dlp to prevent freezing the server
def run_yt_dlp(ydl_opts, url):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info, ydl.prepare_filename(info)

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

    # 1. Dedicated TikTok Logic
    if any(domain in url for domain in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]):
        data = await asyncio.to_thread(fetch_tiktok_data, url)
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

    # 2. General Downloader (Fallback for TikTok, YouTube, FB, IG)
    ydl_opts = {
        'format': 'bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    try:
        # Run yt-dlp in a separate thread so it won't block the async loop
        loop = asyncio.get_running_loop()
        info, file_path = await loop.run_in_executor(None, run_yt_dlp, ydl_opts, url)

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

# Web Server Route for Render / UptimeRobot Health Check
async def handle_ping(request):
    return web.Response(text="Bot status: ONLINE")

async def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # Build Telegram Bot App
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))

    # Build Web Server for Render & UptimeRobot
    web_app = web.Application()
    web_app.router.add_get('/', handle_ping)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

    # Start Bot Polling
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    # Keep running forever
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
