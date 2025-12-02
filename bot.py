import discord
import os
from dotenv import load_dotenv
import json

# 加载 .env 文件中的环境变量
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# 创建一个 Intents 对象并启用所需权限
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.reactions = True
intents.voice_states = True

# 根据环境变量决定是否使用代理
proxy_url = os.getenv('HTTP_PROXY')
if proxy_url:
    print(f"检测到代理，将使用: {proxy_url}")
    client = discord.Client(intents=intents, proxy=proxy_url)
else:
    print("未检测到代理，将直接连接")
    client = discord.Client(intents=intents)

# --- 作品精选功能配置 ---
GALLERY_CHANNEL_NAME = "作品精选"
TRIGGER_EMOJI = "👍"
PROCESSED_EMOJI = "✅"
AUTHOR_THREADS_FILE = "author_threads.json"

# --- 辅助函数：加载和保存作者帖子数据 ---
def load_author_threads():
    if not os.path.exists(AUTHOR_THREADS_FILE):
        return {}
    with open(AUTHOR_THREADS_FILE, 'r') as f:
        return json.load(f)

def save_author_threads(data):
    with open(AUTHOR_THREADS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- 事件监听 ---
@client.event
async def on_ready():
    print(f'我们已经以 {client.user} 身份登录')

@client.event
async def on_member_join(member):
    # 自动分配 "观众" 角色
    try:
        role = discord.utils.get(member.guild.roles, name="👀 观众")
        if role:
            await member.add_roles(role)
            print(f'已为 {member.name} 分配角色 "👀 观众"')
        else:
            print('未找到名为 "👀 观众" 的角色，请在服务器中创建。')
    except Exception as e:
        print(f'分配角色时出错: {e}')

@client.event
async def on_member_remove(member):
    # 查找名为 "聊天" 的频道
    channel = discord.utils.get(member.guild.text_channels, name="聊天")
    if channel is not None:
        await channel.send(f'成员 {member.name}#{member.discriminator} 已经离开了服务器。')

@client.event
async def on_message(message):
    if message.author == client.user or not message.guild:
        return

    # --- 一次性设置服务器现有成员角色 ---
    if message.content == '!setup_roles':
        if not message.author.guild_permissions.administrator:
            await message.channel.send("抱歉，只有管理员才能执行此命令。")
            return

        spectator_role = discord.utils.get(message.guild.roles, name="👀 观众")
        creator_role = discord.utils.get(message.guild.roles, name="🎨 创作者")

        if not spectator_role:
            await message.channel.send("错误：未找到“👀 观众”角色，请先创建。")
            return

        updated_count = 0
        await message.channel.send("正在为现有成员分配初始角色，这可能需要一些时间...")

        for member in message.guild.members:
            if member.bot:
                continue
            
            if spectator_role not in member.roles and (not creator_role or creator_role not in member.roles):
                try:
                    await member.add_roles(spectator_role)
                    updated_count += 1
                    print(f"已为现有成员 {member.name} 分配角色 '👀 观众'")
                except Exception as e:
                    print(f"为 {member.name} 分配角色时出错: {e}")
        
        await message.channel.send(f"操作完成！共为 {updated_count} 名现有成员分配了“👀 观众”角色。")
        return

    if message.content == 'ping':
        await message.channel.send('pong')
        return

    spectator_role = discord.utils.get(message.guild.roles, name="👀 观众")
    creator_role = discord.utils.get(message.guild.roles, name="🎨 创作者")

    if spectator_role and creator_role and spectator_role in message.author.roles:
        if message.attachments:
            try:
                await message.author.remove_roles(spectator_role)
                await message.author.add_roles(creator_role)
                print(f'用户 {message.author.name} 已升级为 "🎨 创作者"')
                await message.channel.send(f'恭喜 {message.author.mention} 发布了作品，成功晋级为 🎨 创作者！')
            except Exception as e:
                print(f'为 {message.author.name} 升级角色时出错: {e}')

@client.event
async def on_raw_reaction_add(payload):
    if payload.user_id == client.user.id or str(payload.emoji) != TRIGGER_EMOJI:
        return

    guild = client.get_guild(payload.guild_id)
    if not guild: return

    reactor = guild.get_member(payload.user_id)
    if not reactor: return

    channel = guild.get_channel(payload.channel_id)
    if not channel: return
    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.NotFound:
        return

    if not message.attachments: return

    for reaction in message.reactions:
        if reaction.emoji == PROCESSED_EMOJI and reaction.me:
            return

    gallery_channel = discord.utils.get(guild.forums, name=GALLERY_CHANNEL_NAME)
    if not gallery_channel:
        print(f"错误：未找到名为 '{GALLERY_CHANNEL_NAME}' 的论坛频道。")
        return

    author_id = str(message.author.id)
    author_threads = load_author_threads()

    embed = discord.Embed(
        description=f"[跳转到原消息]({message.jump_url})",
        color=discord.Color.gold()
    )
    embed.set_author(name=f"作者：{message.author.display_name}", icon_url=message.author.display_avatar.url)
    embed.set_image(url=message.attachments[0].url)
    embed.set_footer(text=f"在 #{channel.name} 中由 {reactor.display_name} 精选")
    embed.timestamp = message.created_at

    try:
        if author_id in author_threads:
            thread_id = author_threads[author_id]
            try:
                thread = guild.get_thread(thread_id) or await guild.fetch_channel(thread_id)
                if thread:
                    await thread.send(embed=embed)
                else:
                    raise discord.NotFound
            except (discord.NotFound, discord.Forbidden):
                thread_name = f"{message.author.display_name} 的作品集"
                new_thread_obj = await gallery_channel.create_thread(name=thread_name, embed=embed)
                author_threads[author_id] = new_thread_obj.thread.id
                save_author_threads(author_threads)
        else:
            thread_name = f"{message.author.display_name} 的作品集"
            new_thread_obj = await gallery_channel.create_thread(name=thread_name, embed=embed)
            author_threads[author_id] = new_thread_obj.thread.id
            save_author_threads(author_threads)
        
        await message.add_reaction(PROCESSED_EMOJI)
    except Exception as e:
        print(f"处理作品精选时出错: {e}")

@client.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    notification_channel = discord.utils.get(member.guild.text_channels, name="聊天")
    if not notification_channel:
        print("错误：未找到名为 '聊天' 的通知频道。")
        return

    if before.channel is None and after.channel is not None:
        await notification_channel.send(f"🎤 {member.display_name} 进入了语音频道 **{after.channel.name}**。")
    elif before.channel is not None and after.channel is None:
        await notification_channel.send(f"🔇 {member.display_name} 离开了语音频道 **{before.channel.name}**。")

# 运行机器人
client.run(TOKEN)
