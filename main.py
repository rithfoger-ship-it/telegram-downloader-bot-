import os
import logging
import asyncio
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Track unique active users
user_set = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    welcome_text = (
        f"🤖 **FOGER Downloader Bot**\n"
        f"👥 *Active Users:* `{len(user_set)} users`\n\n"
        f"Send me any link from TikTok, Facebook, Instagram, or YouTube to download!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    status_msg = await update.message.reply_text("🔄 Processing your link... Please wait!")

    # Format logic: Strictly selects video under 45MB to avoid Telegram's 50MB ceiling limit
    ydl_opts = {
        'format': 'bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract entry if it's a playlist wrapper
            if 'entries' in info:
                info = info['entries'][0]

            # 1. Handle Photo Slideshows (TikTok / IG Multi-Photo posts)
            images = info.get('images', [])
            if not images and info.get('_type') == 'playlist':
                images = [entry.get('url') for entry in info.get('entries', []) if entry.get('url')]

            if images:
                await status_msg.edit_text("📸 Downloading images...")
                media_group = []
                
                # Send maximum 10 images per album (Telegram API limit)
                for i, img_url in enumerate(images[:10]):
                    if i == 0:
                        media_group.append(
                            InputMediaPhoto(media=img_url, caption="Downloaded via @FOGER_downloader_bot")
                        )
                    else:
                        media_group.append(InputMediaPhoto(media=img_url))
                
                await update.message.reply_media_group(media=media_group)
                await status_msg.delete()
                return

            # 2. Handle Video Downloading
            await status_msg.edit_text("📥 Downloading video...")
            download_info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(download_info)

            # Ensure file exists and enforce the 50MB check
            if os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                
                if file_size_mb > 49.5:
                    await status_msg.edit_text("⚠️ Video file is too large to send via Telegram (>50MB).")
                    os.remove(file_path)
                    return

                await status_msg.edit_text("📤 Uploading to Telegram...")
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="Downloaded via @FOGER_downloader_bot"
                    )
                
                # Cleanup local file after sending
                os.remove(file_path)
                await status_msg.delete()

    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
        await status_msg.edit_text("❌ Failed to download media. Please make sure the link is valid and public.")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))

    print("Bot is up and running...")
    app.run_polling()

if __name__ == '__main__':
    main()
