# bot.py
# Bot sencillo de fichaje (entrar / salir) usando discord.py y SQLite.
# Asegúrate de haber instalado discord.py y python-dotenv y de tener activado el venv.

import os
import sqlite3
from datetime import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()  # carga variables desde .env
TOKEN = os.getenv("DISCORD_TOKEN")
REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID", "0"))

DB_FILE = "sams_shifts.db"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# BD (SQLite)
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_name TEXT,
        character_name TEXT,
        department TEXT,
        start_ts TEXT NOT NULL,
        end_ts TEXT,
        duration_minutes INTEGER,
        week_year TEXT
    );
    """)
    conn.commit()
    conn.close()

def insert_start(user_id, user_name, character_name, department, start_ts):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO shifts (user_id, user_name, character_name, department, start_ts) VALUES (?,?,?,?,?)",
              (user_id, user_name, character_name, department, start_ts))
    conn.commit()
    conn.close()

def close_shift_and_record(user_id, end_ts):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, start_ts FROM shifts WHERE user_id = ? AND end_ts IS NULL ORDER BY start_ts DESC LIMIT 1", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    shift_id, start_ts_str = row
    start_dt = datetime.fromisoformat(start_ts_str)
    end_dt = end_ts
    duration = end_dt - start_dt
    duration_minutes = int(duration.total_seconds() // 60)
    iso = end_dt.isocalendar()
    week_year = f"{iso[0]}-W{iso[1]:02d}"
    c.execute("UPDATE shifts SET end_ts = ?, duration_minutes = ?, week_year = ? WHERE id = ?",
              (end_dt.isoformat(), duration_minutes, week_year, shift_id))
    conn.commit()
    conn.close()
    return {"duration_minutes": duration_minutes, "start": start_dt, "end": end_dt, "week_year": week_year}

def sum_week_minutes_for_user(user_id, week_year):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT SUM(duration_minutes) FROM shifts WHERE user_id = ? AND week_year = ?", (user_id, week_year))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0

def get_weekly_totals(week_year):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_name, character_name, SUM(duration_minutes) as total FROM shifts WHERE week_year = ? GROUP BY user_id ORDER BY total DESC", (week_year,))
    rows = c.fetchall()
    conn.close()
    return rows

# ----------------------------
# Eventos y comandos
# ----------------------------
@bot.event
async def on_ready():
    init_db()
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"Bot listo. Conectado como {bot.user} (id: {bot.user.id})")
    if not weekly_report_task.is_running():
        weekly_report_task.start()

@bot.tree.command(name="entrar", description="Fichar entrada en servicio (IC)")
@discord.app_commands.describe(character="Nombre del personaje", department="Departamento (ej: Urgencias)")
async def entrar(interaction: discord.Interaction, character: str, department: str):
    user = interaction.user
    start = datetime.utcnow()
    insert_start(user.id, str(user), character, department, start.isoformat())
    await interaction.response.send_message(f"✅ `{character}` fichado ENTRADA en **{department}** a (UTC) {start.isoformat()} — recuerda usar `/salir` al terminar.", ephemeral=True)

@bot.tree.command(name="salir", description="Fichar salida de servicio (IC)")
async def salir(interaction: discord.Interaction):
    user = interaction.user
    end = datetime.utcnow()
    res = close_shift_and_record(user.id, end)
    if res is None:
        await interaction.response.send_message("⚠️ No tienes ningún turno abierto. Usa `/entrar` antes de `/salir`.", ephemeral=True)
        return
    mins = res["duration_minutes"]
    hrs = mins // 60
    rem = mins % 60
    await interaction.response.send_message(f"🟢 Salida registrada. Tiempo trabajado: **{hrs}h {rem}m**. (Semana {res['week_year']})", ephemeral=True)

@bot.tree.command(name="horas_semana", description="Muestra tus horas acumuladas en la semana actual")
async def horas_semana(interaction: discord.Interaction):
    now = datetime.utcnow()
    iso = now.isocalendar()
    week_year = f"{iso[0]}-W{iso[1]:02d}"
    mins = sum_week_minutes_for_user(interaction.user.id, week_year)
    hrs = mins // 60
    rem = mins % 60
    await interaction.response.send_message(f"📅 Horas en {week_year}: **{hrs}h {rem}m**", ephemeral=True)

@tasks.loop(hours=24)
async def weekly_report_task():
    now = datetime.utcnow()
    if now.weekday() != 6:
        return
    iso = now.isocalendar()
    week_year = f"{iso[0]}-W{iso[1]:02d}"
    rows = get_weekly_totals(week_year)
    if not rows:
        return
    text = f"📊 **Informe semanal {week_year}**\n"
    for i, (user_name, char_name, total_min) in enumerate(rows, start=1):
        hrs = int(total_min) // 60
        rem = int(total_min) % 60
        text += f"{i}. **{char_name}** ({user_name}) — {hrs}h {rem}m\n"
    if REPORT_CHANNEL_ID:
        channel = bot.get_channel(REPORT_CHANNEL_ID)
        if channel:
            await channel.send(text)
        else:
            print("REPORT_CHANNEL_ID configurado, pero el bot no encuentra el canal.")
    else:
        print("REPORT_CHANNEL_ID no configurado. Informe semanal:\n", text)

if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: Pon tu token en la variable de entorno DISCORD_TOKEN o en .env")
    else:
        bot.run(TOKEN)
