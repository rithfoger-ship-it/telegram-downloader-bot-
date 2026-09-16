import os
import logging
import asyncio
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Logging Configuration
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Stat Tracking (In-memory simple user counter)
user_set = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    msg = (
        f"🤖 **FOGER Downloader Bot**\n"
        f"👥 *Active Users:* `{len(user_set)} users`\n\n"
        f"ផ្ញើ Link វីដេអូ ឬរូបភាព (TikTok, FB, IG, YouTube) មកទីនេះដើម្បីដោនឡូត!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def process_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    user_set.add(user_id)
    
    status_msg = await update.message.reply_text("🔄 កំពុងដំណើការ... សូមរង់ចាំបន្តិច!")

    # Quality fallback logic to strictly stay under Telegram's 50MB limit
    ydl_opts = {
        'format': 'bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Handle Photo Slideshows (TikTok / IG Photos)
            if 'entries' in info:
                info = info['entries'][0]

            # Check if link contains images instead of video
            images = info.get('images', [])
            if not images and info.get('_type') == 'playlist':
                images = [entry.get('url') for entry in info.get('entries', []) if entry.get('url')]

            if images:
                await status_msg.edit_text("📸 កំពុងទាញយករូបភាព...")
                media_group = []
                for i, img_url in enumerate(images[:10]):  # Telegram limit 10 photos per group
                    if i == 0:
                        media_group.append(InputMediaPhoto(media=img_url, caption="Downloaded via @FOGER_downloader_bot"))
                    else:
                        media_group.append(InputMediaPhoto(media=img_url))
                
                await update.message.reply_media_group(media=media_group)
                await status_msg.delete()
                return

            # Handle Video Download
            await status_msg.edit_text("📥 កំពុងទាញយកវីដេអូ...")
            download_info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(download_info)

            # Double Check File Size
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path) / (1024 * 1024)
                if file_size > 49.5:
                    await status_msg.edit_text("⚠️ វីដេអូនេះធំពេកមិនអាចផ្ញើបាន។")
                    os.remove(file_path)
                    return

                await status_msg.edit_text("📤 កំពុងផ្ញើចូល Telegram...")
                with open(file_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption="Downloaded via @FOGER_downloader_bot"
                    )
                
                # Cleanup file
                os.remove(file_path)
                await status_msg.delete()

    except Exception as e:
        logging.error(f"Error processing link: {e}")
        await status_msg.edit_text("❌ មិនអាចទាញយកបានទេ! សូមពិនិត្យមើល Link ឬសាកល្បង Link ផ្សេង។")

def main():
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_media))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
