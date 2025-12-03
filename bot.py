import discord
import os
from dotenv import load_dotenv
import json
import datetime
from discord.ext import tasks

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

# --- 配置 ---
GALLERY_CHANNEL_NAME = "作品精选"
TRIGGER_EMOJI = "👍"
PROCESSED_EMOJI = "✅"
AUTHOR_THREADS_FILE = "author_threads.json"
CURRENCY_DATA_FILE = "currency_data.json"
STAR_ROLE_NAME = "  "
main_guild = None # 用于存储服务器对象

# --- 辅助函数：数据读写 ---
def load_data(filename):
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # 先尝试读取，如果为空文件，直接返回空字典
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"警告：读取或解析 {filename} 时出错: {e}。")
        # 尝试备份损坏的文件
        if os.path.exists(filename):
            try:
                bak_filename = f"{filename}.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
                os.rename(filename, bak_filename)
                print(f"已将损坏的文件备份为: {bak_filename}")
            except Exception as bak_e:
                print(f"备份文件时出错: {bak_e}")
        return {}

def save_data(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- 事件监听 ---
@client.event
async def on_ready():
    global main_guild
    print(f'我们已经以 {client.user} 身份登录')
    if client.guilds:
        main_guild = client.guilds[0]
        print(f"机器人已在服务器 '{main_guild.name}' (ID: {main_guild.id}) 中准备就绪。")
        
        # 打印功能列表
        print("\n--- 机器人功能列表 ---")
        print("【自动功能】")
        print("  - 新成员自动分配“👀 观众”角色。")
        print("  - “👀 观众”发布图片后自动升级为“🎨 创作者”。")
        print(f"  - 在任意频道对图片点赞“{TRIGGER_EMOJI}”即可自动收录到“{GALLERY_CHANNEL_NAME}”论坛。")
        print("\n【用户命令】")
        print("  - `签到`：每日签到获取 10 画泥。")
        print("  - `我的画泥`：查询当前画泥余额。")
        print(f"  - `购买周星`：花费 10 画泥购买“{STAR_ROLE_NAME}”角色（有效期7天）。")
        print("\n【管理员命令】")
        print("  - `设置初始角色`：为服务器内所有无角色的成员批量分配“👀 观众”角色。")
        print("-----------------------\n")

        check_temp_roles.start()
    else:
        print("错误：机器人未加入任何服务器。")

@client.event
async def on_member_join(member):
    try:
        role = discord.utils.get(member.guild.roles, name="👀 观众")
        if role:
            await member.add_roles(role)
            print(f'已为 {member.name} 分配角色 "👀 观众"')
    except Exception as e:
        print(f'分配角色时出错: {e}')

@client.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="聊天")
    if channel is not None:
        await channel.send(f'成员 {member.name}#{member.discriminator} 已经离开了服务器。')

@client.event
async def on_message(message):
    if message.author == client.user or not message.guild:
        return

    # --- 中文命令处理 ---
    user_id = str(message.author.id)
    currency_data = load_data(CURRENCY_DATA_FILE)
    if user_id not in currency_data:
        currency_data[user_id] = {"balance": 0, "last_signed": ""}

    # 签到
    if message.content == '签到':
        today = str(datetime.date.today())
        if currency_data[user_id].get("last_signed") != today:
            currency_data[user_id]["balance"] += 10
            currency_data[user_id]["last_signed"] = today
            save_data(currency_data, CURRENCY_DATA_FILE)
            await message.channel.send(f"签到成功！你获得了 10 个画泥，现在共有 {currency_data[user_id]['balance']} 个画泥。")
        else:
            await message.channel.send("你今天已经签过到了，明天再来吧！")
        return

    # 我的画泥
    if message.content == '我的画泥':
        balance = currency_data[user_id].get("balance", 0)
        await message.channel.send(f"你当前拥有 {balance} 个画泥。")
        return

    # 购买周星
    if message.content == '购买周星':
        user_balance = currency_data[user_id].get("balance", 0)
        cost = 10
        if user_balance >= cost:
            currency_data[user_id]["balance"] -= cost
            star_role = discord.utils.get(message.guild.roles, name=STAR_ROLE_NAME)
            if not star_role:
                await message.channel.send(f"错误：未找到名为 '{STAR_ROLE_NAME}' 的角色。")
                return
            try:
                await message.author.add_roles(star_role)
                expiry_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
                if "temp_roles" not in currency_data[user_id]:
                    currency_data[user_id]["temp_roles"] = {}
                currency_data[user_id]["temp_roles"]["star_of_the_week"] = expiry_time.isoformat()
                save_data(currency_data, CURRENCY_DATA_FILE)
                await message.channel.send(f"恭喜！你已成功购买 '{STAR_ROLE_NAME}' 角色，有效期7天。消费 10 画泥，剩余 {currency_data[user_id]['balance']} 画泥。")
            except discord.Forbidden:
                await message.channel.send("错误：机器人权限不足，无法为你添加角色。")
        else:
            await message.channel.send(f"你的画泥不足！购买需要 {cost} 画泥，你只有 {user_balance} 画泥。")
        return
    
    # 设置初始角色
    if message.content == '设置初始角色':
        if not message.author.guild_permissions.administrator:
            await message.channel.send("抱歉，只有管理员才能执行此命令。")
            return

        spectator_role = discord.utils.get(message.guild.roles, name="👀 观众")
        creator_role = discord.utils.get(message.guild.roles, name="🎨 创作者")

        if not spectator_role:
            await message.channel.send("错误：未找到“👀 观众”角色，请先创建。")
            return

        updated_count = 0
        total_members_checked = 0
        await message.channel.send("正在获取服务器成员列表并分配初始角色，这可能需要一些时间...")

        try:
            async for member in message.guild.fetch_members(limit=None):
                total_members_checked += 1
                if member.bot:
                    continue

                has_spectator = spectator_role in member.roles
                has_creator = creator_role and creator_role in member.roles

                # 如果成员没有任何关键角色，则分配
                if not has_spectator and not has_creator:
                    try:
                        await member.add_roles(spectator_role)
                        updated_count += 1
                        print(f"已为现有成员 {member.name} 分配角色 '👀 观众'")
                    except discord.Forbidden:
                        print(f"[权限错误] 无法为 {member.name} 分配角色。请检查机器人的角色是否拥有'管理角色'权限，并且其位置高于'👀 观众'角色。")
                    except Exception as e:
                        print(f"为 {member.name} 分配角色时发生未知错误: {e}")
        except discord.Forbidden:
            await message.channel.send("错误：机器人缺少'查看服务器成员'的权限，无法获取成员列表。请检查机器人权限。")
            return
            
        await message.channel.send(f"操作完成！共检查了 {total_members_checked} 名成员，为 {updated_count} 名成员分配了“👀 观众”角色。")
        return
    
    # ping
    if message.content == 'ping':
        await message.channel.send('pong')
        return

    # --- 角色自动升级逻辑 ---
    if message.attachments:
        spectator_role = discord.utils.get(message.guild.roles, name="👀 观众")
        creator_role = discord.utils.get(message.guild.roles, name="🎨 创作者")
        
        # 检查用户是否是“观众”并且还不是“创作者”
        if spectator_role and creator_role and spectator_role in message.author.roles and creator_role not in message.author.roles:
            try:
                # 同时执行移除和添加操作
                await message.author.remove_roles(spectator_role, reason="升级为创作者")
                await message.author.add_roles(creator_role, reason="发布了第一个作品")
                await message.channel.send(f'恭喜 {message.author.mention} 发布了作品，成功晋级为 🎨 创作者！')
                print(f"用户 {message.author.name} 已从 '👀 观众' 升级为 '🎨 创作者'。")
            except discord.Forbidden:
                print(f"[权限错误] 无法为 {message.author.name} 升级角色。请检查机器人角色位置和'管理角色'权限。")
            except Exception as e:
                print(f'为 {message.author.name} 升级角色时发生未知错误: {e}')

@client.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji) != TRIGGER_EMOJI:
        return

    channel = await client.fetch_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    # 确保消息有附件且不是机器人自己发的
    if not message.attachments or message.author.bot:
        return

    # 检查机器人是否已经处理过这个消息
    for reaction in message.reactions:
        if reaction.emoji == PROCESSED_EMOJI and reaction.me:
            print(f"消息 {message.id} 已被标记为处理过，跳过。")
            return

    gallery_channel = discord.utils.get(message.guild.channels, name=GALLERY_CHANNEL_NAME)
    if not gallery_channel or not isinstance(gallery_channel, discord.ForumChannel):
        print(f"错误：未找到名为 '{GALLERY_CHANNEL_NAME}' 的论坛频道。")
        return

    author = message.author
    author_id = str(author.id)
    
    print(f"[DEBUG] 开始处理作者 {author.name} (ID: {author_id}) 的点赞。")
    author_threads = load_data(AUTHOR_THREADS_FILE)
    print(f"[DEBUG] 加载的 author_threads.json 内容: {author_threads}")

    thread_id = author_threads.get(author_id)
    print(f"[DEBUG] 为作者ID {author_id} 查找到的帖子ID是: {thread_id}")
    thread = None

    if thread_id:
        try:
            thread = await client.fetch_channel(thread_id)
        except discord.NotFound:
            print(f"找不到帖子 ID: {thread_id}，将为 {author.name} 创建新帖。")
            thread_id = None # 强制重新创建

    if not thread_id:
        try:
            thread, _ = await gallery_channel.create_thread(
                name=f"{author.display_name}的个人作品集",
                content=f"欢迎来到 {author.mention} 的个人作品集！这里会收录他/她被点赞的优秀作品。",
                applied_tags=[] # 如果有标签可以加
            )
            author_threads[author_id] = thread.id
            print(f"[DEBUG] 准备保存新的 author_threads 数据: {author_threads}")
            save_data(author_threads, AUTHOR_THREADS_FILE)
            print(f"为 {author.name} 创建了新的作品集帖子。")
        except Exception as e:
            print(f"创建帖子时出错: {e}")
            return
    
    if thread:
        try:
            image_url = message.attachments[0].url
            embed = discord.Embed(
                description=f"**原消息链接：** [点击跳转]({message.jump_url})",
                color=discord.Color.blue()
            )
            embed.set_image(url=image_url)
            embed.set_author(name=f"作者：{author.display_name}", icon_url=author.display_avatar.url)
            embed.set_footer(text=f"发布于：{message.created_at.strftime('%Y-%m-%d %H:%M')}")
            
            await thread.send(embed=embed)
            print(f"已将 {author.name} 的作品添加到其作品集中。")
            
            # 添加处理完成的标记
            await message.add_reaction(PROCESSED_EMOJI)

        except Exception as e:
            print(f"发送作品到帖子时出错: {e}")

# --- 后台任务：检查临时角色到期 ---
@tasks.loop(hours=1)
async def check_temp_roles():
    if not main_guild:
        return
    print("[TASK] 开始检查临时角色到期...")
    currency_data = load_data(CURRENCY_DATA_FILE)
    current_time = datetime.datetime.now(datetime.timezone.utc)
    users_to_update = list(currency_data.keys())
    for user_id in users_to_update:
        user_data = currency_data.get(user_id, {})
        if "temp_roles" in user_data:
            roles_to_remove = []
            for role_key, expiry_iso in list(user_data["temp_roles"].items()):
                expiry_time = datetime.datetime.fromisoformat(expiry_iso)
                # 确保 expiry_time 是 aware 的，如果它不是
                if expiry_time.tzinfo is None:
                    expiry_time = expiry_time.replace(tzinfo=datetime.timezone.utc)

                if current_time >= expiry_time:
                    roles_to_remove.append(role_key)
                    member = main_guild.get_member(int(user_id))
                    if member and role_key == "star_of_the_week":
                        role_to_remove = discord.utils.get(main_guild.roles, name=STAR_ROLE_NAME)
                        if role_to_remove and role_to_remove in member.roles:
                            try:
                                await member.remove_roles(role_to_remove)
                                print(f"用户 {member.name} 的 '{STAR_ROLE_NAME}' 角色已到期并移除。")
                            except discord.Forbidden:
                                print(f"权限不足，无法移除 {member.name} 的到期角色。")
            for role_key in roles_to_remove:
                del currency_data[user_id]["temp_roles"][role_key]
            if not currency_data[user_id]["temp_roles"]:
                del currency_data[user_id]["temp_roles"]
    save_data(currency_data, CURRENCY_DATA_FILE)
    print("[TASK] 临时角色检查完成。")

# 运行机器人
client.run(TOKEN)
