from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ConversationHandler, MessageHandler, filters

from interactions.utils import TIMEOUT_DURATION, handle_interaction_timeout, handle_interaction_cancel
from services.conversion_service import VIDEO_TYPES, convert_video, input_media_exist, clean_up_media
from services.message_service import update_message, send_document, send_message
from ui.builder import show_conversion_options


def handle_video_input():
    """
    Handles video input from user.
    """
    return ConversationHandler(
        entry_points=[MessageHandler(filters.VIDEO, get_uploaded_video)],
        states={
            1: [CallbackQueryHandler(handle_video_output, pattern='video_(\S+)_(\S+)')],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, handle_interaction_timeout)]
        },
        fallbacks=[CallbackQueryHandler(handle_interaction_cancel, pattern='cancel')],
        conversation_timeout=TIMEOUT_DURATION
    )


async def get_uploaded_video(update, context):
    """
    Captures uploaded videos.
    Args:
        update: default telegram arg
        context: default telegram arg
    """
    file_id = update.message.video.file_id
    input_type = update.message.video.mime_type[6:]

    chat_id = update.message.chat_id
    await process_upload_as_video(context, chat_id, file_id, input_type)
    return 1


async def process_upload_as_video(context, chat_id, file_id, input_type):
    """
    Processes the uploaded file as a video and prompts the user for conversion type.
    Args:
        context: default telegram arg
        chat_id: id of user who uploaded the media
        file_id: id identifying uploaded file
        input_type: type of file sent
    """
    receiving_msg = await send_message(context, chat_id, "Video file detected. Preparing file...")
    new_file = await context.bot.get_file(file_id)
    with open(f"./input_media/{chat_id}.{input_type}", "wb") as file:
        await new_file.download_to_memory(file)
    reply_markup = show_conversion_options(VIDEO_TYPES, "video", input_type)
    await update_message(receiving_msg, "Please select the file type to convert to:", markup=reply_markup)


async def handle_video_output(update, context):
    """
    Performs conversion upon user's selection of desired output video type and returns the final result.
    Args:
        update: default telegram arg
        context: default telegram arg
    """
    await context.bot.answer_callback_query(update.callback_query.id)
    data = update.callback_query.data
    chat_id = update.callback_query.message.chat.id

    # update user on progress of conversion and send converted media on success
    try:
        match_file = data.split("_")
        input_type, output_type = match_file[1], match_file[2]
        if not input_media_exist(chat_id, input_type):
            await send_message(context, chat_id, "File not found, please upload again.")
            return ConversationHandler.END

        processing_msg = await send_message(context, chat_id, f"Converting {input_type,} file to {output_type}...")
        convert_video(chat_id, input_type, output_type)
        await update_message(processing_msg, f"Converted to {output_type} format. Retrieving file...")
        await send_document(context, chat_id, f"./output_media/{chat_id}.{output_type}", "Here is your file!")
    # throw error on failure
    except Exception as ex:
        await update_message(processing_msg, 'An error has occurred. Please open an issue at our <a href="https://github.com/tjtanjin/simple-media-converter">Project Repository</a>!', parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        print(ex)
    # remove all media files at the end
    finally:
        clean_up_media(chat_id, input_type, output_type)
    return ConversationHandler.END


