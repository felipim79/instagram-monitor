# infinity_pollingimport requests
import time
import schedule
import datetime
import json
import os
import threading
import telebot
from telebot.types import Message

# ================== CONFIGURAÇÕES ==================
TELEGRAM_TOKEN = "8749670946:AAH2nEVwTdeRefsdQOjXj426IqW_AeEcmfo"
CHAT_ID = -5514378743

CHECK_INTERVAL_MINUTES = 5

PROFILES_FILE = "monitored_profiles.json"
STATE_FILE = "instagram_state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Carregar perfis salvos
def load_profiles():
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_profiles(profiles):
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

monitored_profiles = load_profiles()

# ====================== FUNÇÃO PARA MENCIONAR MEMBROS ======================
def get_all_mentions():
    mentions = []
    try:
        admins = bot.get_chat_administrators(CHAT_ID)
        for admin in admins:
            if admin.user.username:
                mentions.append(f"@{admin.user.username}")
            else:
                mentions.append(f"[{admin.user.first_name}](tg://user?id={admin.user.id})")
    except:
        pass
    
    if not mentions:
        mentions.append("@everyone @all")
    
    return " ".join(mentions[:25])  # Limite seguro

# ====================== COMANDOS ======================

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message: Message):
    text = "👋 **Monitor de Instagram Ativo**\n\nComandos:\n/insta - Adicionar perfis\n/list - Ver lista\n/remove - Remover"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['insta'])
def cmd_insta(message: Message):
    bot.reply_to(message, "🔗 Envie o link ou @ do Instagram (pode mandar vários):")
    bot.register_next_step_handler(message, process_links)

def process_links(message: Message):
    global monitored_profiles
    text = message.text.strip()
    added = []
    for line in text.splitlines():
        for word in line.split():
            word = word.strip()
            if not word: continue
            if "instagram.com" in word:
                username = word.split("instagram.com/")[-1].split("/")[0].strip("@/")
            else:
                username = word.strip("@/")
            if username and username not in monitored_profiles:
                monitored_profiles.append(username)
                added.append(username)

    if added:
        save_profiles(monitored_profiles)
        bot.reply_to(message, f"✅ Adicionados:\n" + "\n".join([f"• @{u}" for u in added]))
    else:
        bot.reply_to(message, "Nenhum novo perfil adicionado.")

@bot.message_handler(commands=['list'])
def cmd_list(message: Message):
    if not monitored_profiles:
        bot.reply_to(message, "Nenhum perfil monitorado.")
        return
    text = "📋 **Perfis Monitorados:**\n" + "\n".join([f"• @{u}" for u in monitored_profiles])
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['remove'])
def cmd_remove(message: Message):
    bot.reply_to(message, "🗑️ Envie o @username para remover:")
    bot.register_next_step_handler(message, process_remove)

def process_remove(message: Message):
    global monitored_profiles
    username = message.text.strip().replace("@", "").strip()
    if username in monitored_profiles:
        monitored_profiles.remove(username)
        save_profiles(monitored_profiles)
        bot.reply_to(message, f"✅ @{username} removido.")
    else:
        bot.reply_to(message, "❌ Não encontrado.")

# ====================== MONITOR ======================

def check_profile(username):
    try:
        url = f"https://www.instagram.com/{username}/"
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        
        content = r.text.lower()
        
        error_phrases = [
            "sorry, this page isn't available",
            "page not found",
            "this content isn't available",
            "esta página não está disponível",
            "o link em que você clicou pode não estar funcionando",
            "página pode ter sido removida",
            "esta publicação não está disponível"
        ]
        
        if any(phrase in content for phrase in error_phrases):
            return False, "Perfil caiu"
        
        return True, "OK"
        
    except:
        return False, "Erro"


def monitor_job():
    global monitored_profiles
    if not monitored_profiles:
        return

    state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
        except:
            pass

    for username in monitored_profiles[:]:
        is_up, reason = check_profile(username)
        was_down = state.get(username, False)

        now = datetime.datetime.now().strftime('%d/%m %H:%M')

        if not is_up and not was_down:
            mentions = get_all_mentions()
            
            msg = f"❌ {mentions}\n\n" \
                  f"⚠️ O perfil **@{username}** caiu\n\n" \
                  f"⏰ {now}\n\n" \
                  f"Faça um novo perfil porta link ou vc vai perder dinheiro 💸\n\n" \
                  f"🔗 https://www.instagram.com/{username}/"
            
            try:
                bot.send_message(CHAT_ID, msg, parse_mode="Markdown", disable_web_page_preview=True)
            except:
                bot.send_message(CHAT_ID, f"❌ @everyone @all\n\n⚠️ O perfil **@{username}** caiu\n\nFaça um novo perfil ou vai perder dinheiro 💸", parse_mode="Markdown")
            
            state[username] = True

        elif is_up and was_down:
            state[username] = False

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def run_monitor():
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(monitor_job)
    time.sleep(5)
    monitor_job()
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    print("🚀 Bot iniciado com sucesso! Monitorando a cada 5 minutos.")
    threading.Thread(target=run_monitor, daemon=True).start()
    bot.infinity_polling()
