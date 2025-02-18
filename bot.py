import discord
import random
from discord.ext import commands
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Define bot prefix and intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="/", intents=intents)

roles = {
    "Vanguard": [
        "Bruce Banner / Hulk", "Captain America", "Doctor Strange", "Groot", "Magneto",
        "Peni Parker", "Thor", "Venom"
    ],
    "Duelist": [
        "Black Panther", "Black Widow", "Hawkeye", "Hela", "Iron Fist", "Iron Man",
        "Magik", "Mister Fantastic", "Moon Knight", "Namor", "Psylocke", "Punisher",
        "Scarlet Witch", "Spider-Man", "Squirrel Girl", "Star-Lord", "Storm", "Winter Soldier", "Wolverine"
    ],
    "Strategist": [
        "Adam Warlock", "Cloak & Dagger", "Invisible Woman", "Jeff the Land Shark",
        "Loki", "Luna Snow", "Mantis", "Rocket Raccoon"
    ]
}

# --- Data Persistence (using JSON) ---
DATA_FILE = "player_data.json"

def load_player_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_player_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

player_data = load_player_data()
# --- End Data Persistence ---


def get_random_characters(num_people, available_characters, player_names):
    """Assigns random characters to players, respecting role limits."""
    category_limits = {"Vanguard": 2, "Duelist": 2, "Strategist": 2}
    selected_characters = []
    role_count = {"Vanguard": 0, "Duelist": 0, "Strategist": 0}

    for name in player_names:
        available_roles = [role for role in available_characters if role_count[role] < category_limits[role] and available_characters[role]]
        if not available_roles:
            continue  # Handle edge case
        role = random.choice(available_roles)
        char = random.choice(available_characters[role])
        selected_characters.append((char, role, name))
        available_characters[role].remove(char)
        role_count[role] += 1

    return selected_characters


@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")
    await bot.tree.sync()
    print("Commands synced globally.")



@bot.tree.command(name="start", description="Start the game and add players.")
async def setup(interaction: discord.Interaction,
                player1: str, player2: str = None, player3: str = None,
                player4: str = None, player5: str = None, player6: str = None):
    """Starts a new game and adds players (up to 6)."""

    await interaction.response.defer()
    guild_id = str(interaction.guild_id)
    players = [p for p in [player1, player2, player3, player4, player5, player6] if p] # Create a players list
    num_players = len(players)

    if num_players < 1 or num_players > 6: # Check to make sure number of players is not greater than 6
        await interaction.followup.send("⚠️ You must select between 1 and 6 players.", ephemeral=True)
        return

    if len(set(players)) != num_players:  # Check to make sure that there are not duplicate players
        await interaction.followup.send("⚠️ Duplicate player names are not allowed.", ephemeral=True)
        return

    player_data[guild_id] = {  # Create a dictionary to keep track of all the players
        "players": players,
        "selected_characters": [],
        "num_players": num_players,
        "message_id": None
    }

    save_player_data(player_data)  # Save game data
    await assign_characters(interaction) # Assign the characters


async def assign_characters(context):
    """Assigns characters and updates the assignment message."""
    if isinstance(context, discord.Interaction):
        guild_id = str(context.guild_id)
        followup = context.followup
    else:
        guild_id = str(context.guild.id)
        followup = context.channel.send

    if guild_id not in player_data:
        return

    game_data = player_data[guild_id]
    num_people = game_data["num_players"]
    available_characters = {role: roles[role][:] for role in roles}

    selected_characters = get_random_characters(num_people, available_characters, game_data["players"])
    game_data["selected_characters"] = selected_characters
    save_player_data(player_data)

    embed = discord.Embed(title="Character Assignments", color=discord.Color.green())
    for class_name in ["Vanguard", "Duelist", "Strategist"]:
        char_list = [f"**{name}** → {char}" for char, role, name in selected_characters if role == class_name]
        if char_list:
            embed.add_field(name=f"__{class_name}s__", value="\n".join(char_list), inline=False)

    embed.add_field(name="Reroll", value="React with 🔄 to reroll the characters.", inline=False)

    if game_data["message_id"]:
        try:
            message = await context.channel.fetch_message(game_data["message_id"])
            await message.edit(embed=embed)
            await message.add_reaction("🔄")
        except discord.NotFound:
            game_data["message_id"] = None

    if not game_data["message_id"]:
        if isinstance(context, discord.Interaction):
            message = await context.followup.send(embed=embed) # Use followup.send, not response.send
        else:
            message = await context.channel.send(embed=embed)
        game_data["message_id"] = message.id
        await message.add_reaction("🔄")
    save_player_data(player_data)

@bot.tree.command(name="reroll", description="Re-roll characters for the current game.")
async def reroll(interaction: discord.Interaction):
    """Rerolls the character assignments."""
    guild_id = str(interaction.guild_id)
    if guild_id not in player_data or not player_data[guild_id]["players"]:
        await interaction.response.send_message("⚠️ No game in progress. Use `/setup` first.", ephemeral=True)
        return

    await interaction.response.defer()
    await assign_characters(interaction)


@bot.tree.command(name="reset", description="Reset the game.")
async def reset(interaction: discord.Interaction):
    """Resets the current game."""
    guild_id = str(interaction.guild_id)
    if guild_id in player_data:
        del player_data[guild_id]
        save_player_data(player_data)
        await interaction.response.send_message("✅ Game reset! Use `/setup` to begin again.")
    else:
        await interaction.response.send_message("⚠️ No game to reset.", ephemeral=True)


@bot.event
async def on_reaction_add(reaction, user):
    """Handles the reroll reaction."""
    if reaction.emoji == "🔄" and user != bot.user:
        guild_id = str(reaction.message.guild.id)
        if guild_id in player_data and reaction.message.id == player_data[guild_id]["message_id"]:
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
                await reaction.message.remove_reaction("🔄", bot.user)
            except (discord.errors.NotFound, discord.errors.Forbidden, discord.HTTPException):
                pass  # Already handled potential errors
            await assign_characters(reaction.message)

bot.run(TOKEN)