from bot import (
    aria2, 
    aria2_options, 
    aria2c_global, 
    config_dict, 
    LOGGER, 
    download_dict, 
    download_dict_lock, 
    queue_dict_lock, 
    non_queued_dl
)
from bot.helper.mirror_utils.status_utils.aria2_status import Aria2Status
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import sync_to_async, bt_selection_buttons
# FIXED: Changed files_util to file_utils
from bot.helper.ext_utils.file_utils import aiopath, aioremove

async def add_aria2c_download(link, path, listener, filename, header, ratio, seed_time):
    # --- FIXED: REDIRECT MEGA LINKS ---
    if "mega.nz" in link:
        from bot.helper.mirror_utils.download_utils.mega_download import add_mega_download
        return await add_mega_download(link, path, listener, filename)
    # ----------------------------------

    a2c_opt = {**aria2_options}
    [a2c_opt.pop(k) for k in aria2c_global if k in aria2_options]
    a2c_opt['dir'] = path
    if filename:
        a2c_opt['out'] = filename
    if header:
        a2c_opt['header'] = header
    if ratio:
        a2c_opt['seed-ratio'] = ratio
    if seed_time:
        a2c_opt['seed-time'] = seed_time
    
    if TORRENT_TIMEOUT := config_dict.get('TORRENT_TIMEOUT'):
        a2c_opt['bt-stop-timeout'] = f'{TORRENT_TIMEOUT}'
    
    # Bypass the missing queue check to prevent ModuleNotFoundError
    added_to_queue = False 
            
    try:
        download = (await sync_to_async(aria2.add, link, a2c_opt))[0]
    except Exception as e:
        LOGGER.info(f"Aria2c Download Error: {e}")
        await sendMessage(listener.message, f'{e}')
        return

    if await aiopath.exists(link):
        await aioremove(link)

    if download.error_message:
        error = str(download.error_message).replace('<', ' ').replace('>', ' ')
        LOGGER.info(f"Aria2c Download Error: {error}")
        await sendMessage(listener.message, error)
        return

    gid = download.gid
    name = download.name
    async with download_dict_lock:
        download_dict[listener.uid] = Aria2Status(gid, listener, queued=added_to_queue)
    
    # Logic simplified to skip queueing
    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)
    LOGGER.info(f"Aria2Download started: {name}. Gid: {gid}")

    await listener.onDownloadStart()

    if not listener.select or not config_dict.get('BASE_URL'):
        await sendStatusMessage(listener.message)
    elif listener.select and download.is_torrent and not download.is_metadata:
        await sync_to_async(aria2.client.force_pause, gid)
        SBUTTONS = bt_selection_buttons(gid)
        msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
        await sendMessage(listener.message, msg, SBUTTONS)
