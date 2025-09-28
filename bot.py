import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime

# Cargar variables de entorno
import os

TOKEN = os.environ["BOT_TOKEN"]
REPORT_CHANNEL_ID = int(os.environ["REPORT_CHANNEL_ID"])

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Diccionario global de horas
registro_horas = {}  # {usuario_id: {"nombre": "Nombre Personaje", "minutos": 0}}

# ---------- SLASH COMMANDS ----------

@bot.tree.command(name="entrar", description="Fichar entrada al servicio")
@app_commands.describe(nombre="Nombre de tu personaje", departamento="Departamento al que entras")
async def entrar(interaction: discord.Interaction, nombre: str, departamento: str):
    if interaction.user.id not in registro_horas:
        registro_horas[interaction.user.id] = {"nombre": nombre, "minutos": 0}
    registro_horas[interaction.user.id]["entrada"] = datetime.now()
    await interaction.response.send_message(f"✅ {nombre} ha entrado a servicio en {departamento}.")

@bot.tree.command(name="salir", description="Fichar salida del servicio")
async def salir(interaction: discord.Interaction):
    usuario = registro_horas.get(interaction.user.id)
    if not usuario or "entrada" not in usuario:
        await interaction.response.send_message("❌ No estás en servicio.")
        return

    tiempo_sesion = (datetime.now() - usuario["entrada"]).total_seconds() / 60
    usuario["minutos"] += tiempo_sesion
    del usuario["entrada"]

    await interaction.response.send_message(f"✅ {usuario['nombre']} ha salido de servicio. Tiempo de esta sesión: {int(tiempo_sesion)} minutos.")

@bot.tree.command(name="horas_semana", description="Ver las horas acumuladas de todos los miembros")
async def horas_semana(interaction: discord.Interaction):
    if not registro_horas:
        await interaction.response.send_message("No hay registros aún.")
        return

    mensaje = "📊 Horas acumuladas esta semana:\n"
    for user in registro_horas.values():
        mensaje += f"– {user['nombre']}: {int(user['minutos'])} minutos\n"
    await interaction.response.send_message(mensaje)

# ---------- EVENTOS ----------

@bot.event
async def on_ready():
    # Sincronizar los slash commands con Discord
    await bot.tree.sync()
    print(f"Bot listo. Conectado como {bot.user} (id: {bot.user.id})")

# ---------- RUN BOT ----------
bot.run(TOKEN)

# ----------------- Mantener activo en Render -----------------
import asyncio
from aiohttp import web
import os

async def keep_alive():
    async def handler(request):
        return web.Response(text="Bot activo 24/7")

    app = web.Application()
    app.add_routes([web.get("/", handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))  # Render asigna un PORT automáticamente
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    # Inicia la simulación del puerto y tu bot a la vez
    await keep_alive()
    await bot.start(TOKEN)

asyncio.run(main())

