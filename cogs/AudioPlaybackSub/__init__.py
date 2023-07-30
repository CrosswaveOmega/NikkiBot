from .AudioContainer import AudioContainer, special_playlist_download, speciallistsplitter
from .MessageTemplates_EXT import MessageTemplatesMusic
from .MusicPlayer import MusicPlayer,PlaylistPageContainer
from .MusicPlayerManager import MusicManager
from .MusicViews import PlayerButtons,PlaylistButtons
from .MusicUtils import connection_check, get_audio_directory,get_directory_size
from .MusicDatabase import UserMusicProfile,UserUploads, MusicJSONMemoryDB



async def setup(bot):
    import gui
    gui.print(f"loading in child module {__name__}")

async def teardown(bot):
    import gui
    gui.print(f"unloading child module {__name__}")

