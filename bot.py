import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord import ButtonStyle
import sqlite3
import random
import asyncio
from datetime import datetime
import pandas as pd
from grt_schedule import GRTSchedule
from mineGame import Mines

# Initialize intents
intents = discord.Intents.default()
intents.message_content = True 
# Initialize the bot with intents
bot = commands.Bot(command_prefix="-", intents=intents)

# Initialize the database
conn = sqlite3.connect('blackjack.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 1000
    )
''')
conn.commit()
conn.close()

# Active games per user
active_games = {} 

# Database functions

def get_balance(user_id):
    conn = sqlite3.connect('blackjack.db')
    cursor = conn.cursor()

    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 1000))
        conn.commit()
        balance = 1000
    else:
        balance = result[0]

    conn.close()
    return balance

def update_balance(user_id, amt):
    conn = sqlite3.connect('blackjack.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amt, user_id))
    conn.commit()
    conn.close()

class BlackjackGame:
    def __init__(self, bet):
        self.deck = self.makeDeck()
        self.playerHand = []
        self.dealerHand = []
        self.bet = bet

    def makeDeck(self):
        # Create a deck of 52 cards, 4 suits of 13 cards.
        # Will eventually update to be individual emotes for each card.
        values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        suits = ["♠", "♣", "♥", "♦"]
        deck = [f"{v}{s}" for v in values for s in suits]
        random.shuffle(deck)
        return deck

    def deal_card(self, hand):
        if len(self.deck) == 0:
            self.deck = self.makeDeck()  # [Recreated deck if empty]
        card = self.deck.pop()
        hand.append(card)
        return card

    def hand_value(self, hand):
        value = 0
        aces = 0
        for card in hand:  # [Changed variable name from 'i' to 'card' for clarity]
            card_value = card[:-1]  # [Extracted card value correctly]
            if card_value in ["J", "Q", "K"]:
                value += 10
            elif card_value == "A":
                aces += 1
            else:
                value += int(card_value)

        for _ in range(aces):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
        return value

class BlackjackView(View):
    def __init__(self, game, user_id):
        super().__init__(timeout=20)  
        self.game = game
        self.user_id = user_id
        self.game_over = False  # [Added flag to track game completion]
        self.result = ""  # [Added result message]

        # Initiate interactive game buttons for game actions.
        self.hit_button = Button(label='Hit', style=ButtonStyle.primary)  # [Renamed to snake_case]
        self.stand_button = Button(label='Stand', style=ButtonStyle.success)  # [Renamed to snake_case]
        self.double_down_button = Button(label='Double Down', style=ButtonStyle.secondary)  # [Renamed to snake_case]
        self.split_button = Button(label='Split', style=ButtonStyle.secondary, disabled=True)  # [Renamed to snake_case and disabled]

        self.hit_button.callback = self.hit
        self.stand_button.callback = self.stand
        self.double_down_button.callback = self.double_down
        self.split_button.callback = self.split

        self.add_item(self.hit_button)
        self.add_item(self.stand_button)
        self.add_item(self.double_down_button)
        self.add_item(self.split_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True  # [Ensured only the game owner can interact]

    def create_embed(self):
        """Creates a new embed based on the current game state."""
        if self.game_over:
            description = f"{self.result}"
        else:
            description = "Game In Progress!"

        embed = discord.Embed(title="Blackjack", description=description, color=0xC41E3A)
        embed.add_field(
            name="Your Hand",
            value=" ".join(self.game.playerHand) + f" (Value: {self.game.hand_value(self.game.playerHand)})",
            inline=False
        )  # [Added hand value]

        if self.game_over:
            # Show all dealer cards
            dealer_hand_display = " ".join(self.game.dealerHand) + f" (Value: {self.game.hand_value(self.game.dealerHand)})"
        else:
            # Show only the first dealer card
            if len(self.game.dealerHand) > 0:
                dealer_hand_display = self.game.dealerHand[0] + " [Hidden]"
            else:
                dealer_hand_display = "No cards dealt yet."

        embed.add_field(
            name="Dealer's Hand",
            value=dealer_hand_display,
            inline=False
        )  # [Updated dealer's hand display]
        embed.add_field(
            name="Your Balance",
            value=f"${get_balance(self.user_id)}",
            inline=False
        )  # [Added balance display]
        embed.add_field(
            name="Your Bet",
            value=f"${self.game.bet}",
            inline=False
        )  # [Added bet display]
        return embed

    async def update_embed(self, interaction):
        """Updates the embed message to reflect the current game state."""
        new_embed = self.create_embed()

        if self.game_over:
            # Disable all buttons when the game is over
            for item in self.children:
                item.disabled = True

        await interaction.response.edit_message(embed=new_embed, view=self)  # [Updated embed dynamically]

    async def on_timeout(self):
        """Handles timeout scenario where the user takes too long to respond."""
        if not self.game_over:
            self.game_over = True
            self.result = "You took too long! ❌"
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            # Update the embed message
            channel = bot.get_channel(self.channel_id)  # [Retrieve the channel]
            if channel:
                await channel.send(
                    content=f"<@{self.user_id}> Your game has timed out due to inactivity.",
                    embed=self.create_embed()
                )
            # Remove the game from active_games
            active_games.pop(self.user_id, None)  # [Removed game from active_games]

    async def hit(self, interaction: discord.Interaction):
        # Deal card to player, update hand
        self.game.deal_card(self.game.playerHand)
        player_value = self.game.hand_value(self.game.playerHand)
        if player_value > 21:
            # Player busts
            self.game_over = True  # [Set game over flag]
            self.result = "You busted! ❌"
            await self.update_embed(interaction)  # [Updated embed and disabled buttons]
            active_games.pop(self.user_id, None)  # [Removed game from active_games]
        else:
            await self.update_embed(interaction)  # [Updated embed]

    async def stand(self, interaction: discord.Interaction):
        # Dealer's turn
        while self.game.hand_value(self.game.dealerHand) < 17:
            self.game.deal_card(self.game.dealerHand)

        dealer_value = self.game.hand_value(self.game.dealerHand)
        player_value = self.game.hand_value(self.game.playerHand)

        # Determine outcome
        if dealer_value > 21 or player_value > dealer_value:
            self.result = "You win! ✅"
            update_balance(self.user_id, self.game.bet * 2)  # [Updated balance with winnings]
        elif player_value == dealer_value:
            self.result = "Game result is a push. 🤝"
            update_balance(self.user_id, self.game.bet)  # [Returned bet]
        else:
            self.result = "You lost. ❌"
            # No need to deduct again; bet was already deducted at game start

        self.game_over = True  # [Set game over flag]
        await self.update_embed(interaction)  # [Updated embed and disabled buttons]
        active_games.pop(self.user_id, None)  # [Removed game from active_games]

    async def double_down(self, interaction: discord.Interaction):
        # Double the bet and deal one final card
        user_balance = get_balance(self.user_id)
        if user_balance < self.game.bet:
            await interaction.response.send_message("You don't have enough balance to double down.", ephemeral=True)
            return

        update_balance(self.user_id, -self.game.bet)  # [Deducted additional bet]

        # If balance after deduction is less than 0, set bet to remaining balance
        

        self.game.bet *= 2 
        self.game.deal_card(self.game.playerHand)
        player_value = self.game.hand_value(self.game.playerHand)
        if player_value > 21:
            # Player busts
            self.game_over = True 
            self.result = "You busted! ❌"
            update_balance(self.user_id, -self.game.bet) 
            await self.update_embed(interaction) 
            active_games.pop(self.user_id, None) 
        else:
            # Dealer's turn
            while self.game.hand_value(self.game.dealerHand) < 17:
                self.game.deal_card(self.game.dealerHand)

            dealer_value = self.game.hand_value(self.game.dealerHand)
            player_value = self.game.hand_value(self.game.playerHand)

            # Determine outcome
            if dealer_value > 21 or player_value > dealer_value:
                self.result = "You win! ✅"
                update_balance(self.user_id, self.game.bet * 2)  
            elif player_value == dealer_value:
                self.result = "Game result is a push. 🤝"
                update_balance(self.user_id, self.game.bet)  
            else:
                self.result = "You lost. ❌"

            self.game_over = True 
            await self.update_embed(interaction)  
            active_games.pop(self.user_id, None)  

    async def split(self, interaction: discord.Interaction):
        # Will add shortly
        await interaction.response.send_message("Split is not implemented yet.", ephemeral=True)

# Create the blackjack game command
@bot.command(aliases=['bj'])
async def blackjack(ctx, bet):
    user_id = ctx.author.id

    # Check if the user already has an active game
    if user_id in active_games:
        await ctx.send("You already have an active game! Please finish it before starting a new one.")
        return

    # If bet is "all," set the bet amount to the user's full balance
    if str(bet).lower() == "all":
        bet = get_balance(user_id)
    else:
        try:
            bet = int(bet)
        except ValueError:
            await ctx.send("Please enter a valid bet amount (a number or 'all').")
            return

    # Check if the bet amount is valid
    if bet <= 0:
        await ctx.send("Please enter a valid bet amount greater than $0.")
        return
    elif bet > get_balance(user_id):
        await ctx.send(f"Sorry, you don't have enough balance to bet ${bet}. Your balance: ${get_balance(user_id)}")
        return

    # Deduct the bet from the user's balance at the start of the game
    update_balance(user_id, -bet)

    game = BlackjackGame(bet=bet)

    # Deal initial cards
    game.deal_card(game.playerHand)
    game.deal_card(game.dealerHand)
    game.deal_card(game.playerHand)
    game.deal_card(game.dealerHand)

    # Create the initial embed message showing the game state
    embed = discord.Embed(title="Blackjack", description="Game Started!", color=0xC41E3A)
    embed.add_field(
        name="Your Hand",
        value=" ".join(game.playerHand) + f" (Value: {game.hand_value(game.playerHand)})",
        inline=False
    )  # [Added hand value]

    if len(game.dealerHand) > 0:
        dealer_hand_display = game.dealerHand[0] + " [Hidden]"
    else:
        dealer_hand_display = "No cards dealt yet."

    embed.add_field(
        name="Dealer's Hand",
        value=dealer_hand_display,
        inline=False
    )  # [Updated dealer's hand display]
    embed.add_field(
        name="Your Balance",
        value=f"${get_balance(user_id)}",
        inline=False
    )  # [Added balance display]
    embed.add_field(
        name="Your Bet",
        value=f"${bet}",
        inline=False
    )  # [Added bet display]

    # Initialize the view and send the embed with the view attached
    view = BlackjackView(game, user_id)  # [Initialized BlackjackView with game and user_id]
    view.channel_id = ctx.channel.id  # [Store channel ID in the view]
    active_games[user_id] = view  # [Added game to active_games]
    await ctx.send(embed=embed, view=view)  # [Sent embed with dynamic view]

# Error handler for the blackjack command
@blackjack.error
async def blackjack_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You need to specify a bet amount. Usage: `-blackjack <bet>`")  # [Added error handler]
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Please enter a valid number for the bet amount. Usage: `-blackjack <bet>`")  # [Added handler for bad arguments]
    else:
        await ctx.send("An error occurred. Please try again.")  # [Generic error message]

# Balance command, displays user balance
@bot.command(aliases=['bal', 'b'])
async def balance(ctx):
    user_id = ctx.author.id
    balance = get_balance(user_id)
    await ctx.send(f"Your balance is ``${balance}``")

# Hourly command with cooldown
@bot.command(aliases=['h'])
@commands.cooldown(1, 3600, commands.BucketType.user)  # [Added cooldown: once per hour per user]
async def hourly(ctx):
    user_id = ctx.author.id
    current_balance = get_balance(user_id)
    update_balance(user_id, 100)
    new_balance = get_balance(user_id)
    await ctx.send(f"Your balance has been updated. You received $100. Your new balance is ${new_balance}.")  # [Sent updated balance]

@hourly.error
async def hourly_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes, seconds = divmod(int(error.retry_after), 60)
        await ctx.send(f"Please wait {minutes} minutes and {seconds} seconds before using this command again.")  # [Added cooldown error handler]
    else:
        await ctx.send("An error occurred. Please try again.")  # [Generic error message]

# Daily command with cooldown
@bot.command(aliases=['d'])
@commands.cooldown(1, 86400, commands.BucketType.user)  # [Added cooldown: once per day per user]
async def daily(ctx):
    user_id = ctx.author.id
    current_balance = get_balance(user_id)
    update_balance(user_id, 1000)  # [Corrected amount from 10000 to 1000]
    new_balance = get_balance(user_id)
    await ctx.send(f"Your balance has been updated. You received $1000. Your new balance is ${new_balance}.")  # [Sent updated balance]

@daily.error
async def daily_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours, remainder = divmod(int(error.retry_after), 3600)
        minutes, seconds = divmod(remainder, 60)
        await ctx.send(f"Please wait {hours} hours, {minutes} minutes, and {seconds} seconds before using this command again.")  # [Added cooldown error handler]
    else:
        await ctx.send("An error occurred. Please try again.")  # [Generic error message]

# Give a user a specified amount of money.
@bot.command() 
async def give(ctx, recipient: discord.Member, amount: int):
    sender_id = ctx.author.id
    recipient_id = recipient.id

    if amount <= 0:
        await ctx.send("Please enter a valid amount greater than $0.")
        return

    sender_balance = get_balance(sender_id)
    if sender_balance < amount:
        await ctx.send(f"Sorry, you don't have enough balance to give ``${amount}``. Your balance: ``${sender_balance}``")
        return

    update_balance(sender_id, -amount)
    update_balance(recipient_id, amount)

    sender_new_balance = get_balance(sender_id)
    recipient_new_balance = get_balance(recipient_id)

    await ctx.send(f"You have given ``${amount}`` to ``{recipient}``. Your new balance is ``${sender_new_balance}``. ``{recipient}``'s new balance is ``${recipient_new_balance}``.")  # [Sent transfer confirmation]

# 
@bot.command() # Debugging/admin command. Adds amount specified to balance.
@commands.has_permissions(administrator=True)
async def baladd(ctx, amt: int):
    user_id = ctx.author.id
    current_balance = get_balance(user_id)
    update_balance(user_id, amt)
    new_balance = get_balance(user_id)
    await ctx.send(f"Your balance has been updated. You received ${amt}. Your new balance is ${new_balance}.")

# Displays a leaderboard descending from highest balance to lowest
@bot.command(aliases=['lb'])
async def leaderboard(ctx):
    conn = sqlite3.connect('blackjack.db')
    cursor = conn.cursor()

    cursor.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10')
    results = cursor.fetchall()

    embed = discord.Embed(title="Leaderboard", description="Top 10 Players")
    for index, result in enumerate(results):
        user_id, balance = result
        member = ctx.guild.get_member(user_id)
        if member is None:
            try:
                member = await bot.fetch_user(user_id)
                name = member.name
            except:
                name = "Unknown User"
        else:
            name = member.display_name

        embed.add_field(name=f"{index + 1}. {name}", value=f"${balance}", inline=False)

    conn.close()
    await ctx.send(embed=embed)

# END OF BLACKJACK GAME
# START OF GRT BOT
grt_schedule = GRTSchedule(gtfs_path='gtfs_data/')

@bot.command()
async def grt(ctx, route_number: str, *, stop_name: str):
    response = grt_schedule.get_next_arrivals(route_number, stop_name)
    await ctx.send(response)
# END OF GRT BOT
#START OF MINES GAME
class MinesView(discord.ui.View):
    def __init__(self, ctx, mines_game):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.mines_game = mines_game
        self.user_id = ctx.author.id

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.green)
    async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return

        winnings = int(self.mines_game['amount'] * self.mines_game['multiplier'])
        update_balance(self.user_id, winnings)

        # End the game
        self.mines_game['game_over'] = True
        active_games.pop(self.user_id, None)

        # Disable the button
        button.disabled = True

        # Edit the original message to disable the button
        await interaction.response.edit_message(view=self)

        # Send the cash-out message as a follow-up
        await interaction.followup.send(
            f"You cashed out with a multiplier of x{self.mines_game['multiplier']:.2f}! You won ${winnings}. Your new balance is ${get_balance(self.user_id)}."
        )


@bot.command()
async def mines(ctx, grid_size: int, mine_ct: int, amount: int):
    user_id = ctx.author.id
    current_balance = get_balance(user_id)

    # Check if the user already has an active game
    if user_id in active_games:
        await ctx.send("You already have an active game! Please finish it before starting a new one.")
        return

    if grid_size > 10 or grid_size < 1 or mine_ct < 1 or mine_ct >= grid_size * grid_size:
        await ctx.send("Invalid grid size or mine count. Grid size must be between 1 and 10, and mine count must be less than the total grid positions.")
        return

    if amount <= 0:
        await ctx.send("Please enter a valid bet amount greater than $0.")
        return

    if current_balance < amount:
        await ctx.send(f"Sorry, you don't have enough balance to bet ${amount}. Your current balance is ${current_balance}.")
        return

    # Deduct the bet amount from the user's balance
    update_balance(user_id, -amount)
    game = Mines()

    grid, mine_pos = game.init_grid(grid_size, mine_ct)
    revealed_pos = set()
    gems_revealed = 0
    game_over = False
    grid_message = None
    multiplier = 1.0

    # Create an instance of MinesGame for the user
    mines_game = {
        'grid': grid,
        'mine_pos': mine_pos,
        'revealed_pos': revealed_pos,
        'gems_revealed': gems_revealed,
        'game_over': game_over,
        'grid_message': grid_message,
        'multiplier': multiplier,
        'amount': amount,
        'game': game,
        'grid_size': grid_size,
        'mine_ct': mine_ct
    }
    active_games[user_id] = mines_game

    await ctx.send(f"Starting game with {mine_ct} mines hidden in a {grid_size}x{grid_size} grid. Bet amount: ${amount}")

    # Start the game loop
    await play_mines_game(ctx, mines_game)

async def play_mines_game(ctx, mines_game):
    user_id = ctx.author.id

    def check(message):
        if message.author.id != user_id or message.channel != ctx.channel:
            return False
        # Check if the message content looks like coordinates (e.g., '1,2')
        content = message.content.strip()
        if ',' in content:
            parts = content.split(',')
            if len(parts) == 2:
                try:
                    int(parts[0].strip())
                    int(parts[1].strip())
                    return True
                except ValueError:
                    pass
        return False

    while not mines_game['game_over']:
        # Display the grid
        grid_display = mines_game['game'].display_discord_grid(mines_game['grid'], mines_game['revealed_pos'])

        # Delete the previous grid message
        if mines_game['grid_message']:
            await mines_game['grid_message'].delete()

        # Create an embed with the current multiplier
        embed = discord.Embed(title="Mines Game", description=f"Multiplier: x{mines_game['multiplier']:.2f}", color=0x00FF00)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        # Create a view with a cash-out button
        view = MinesView(ctx, mines_game)

        # Send the grid and embed
        mines_game['grid_message'] = await ctx.send(grid_display, embed=embed, view=view)

        try:
            # Wait for the user's input
            msg = await bot.wait_for('message', check=check, timeout=60)
            input_coords = msg.content.strip()

            # Delete the user's message to keep the chat clean
            await msg.delete()

            # Parse the input coordinates
            try:
                row, col = map(int, input_coords.split(','))
                row -= 1  # Adjust for 0-based indexing
                col -= 1
                if not (0 <= row < mines_game['grid_size'] and 0 <= col < mines_game['grid_size']):
                    await ctx.send("Invalid coordinates. Please enter row and column numbers within the grid size (e.g., '1,2').", delete_after=5)
                    continue
            except ValueError:
                await ctx.send("Invalid input format. Please enter the coordinates as 'row,col' (e.g., '1,2').", delete_after=5)
                continue

            if (row, col) in mines_game['revealed_pos']:
                await ctx.send("Position already revealed! Try again.", delete_after=5)
                continue

            if mines_game['grid'][row][col] == "Mine":
                # Reveal the mine on the grid
                mines_game['revealed_pos'].add((row, col))
                grid_display = mines_game['game'].display_discord_grid(mines_game['grid'], mines_game['revealed_pos'], game_over=True)
                await mines_game['grid_message'].delete()
                embed = discord.Embed(title="Mines Game", description="Boom! You hit a mine. Game Over.", color=0xFF0000)
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
                await ctx.send(grid_display, embed=embed)
                mines_game['game_over'] = True
                active_games.pop(user_id, None)
            else:
                mines_game['revealed_pos'].add((row, col))
                mines_game['gems_revealed'] += 1
                mines_game['multiplier'] = mines_game['game'].mult_calc(
                    mines_game['gems_revealed'], mines_game['mine_ct'], mines_game['grid_size']
                )
                # Continue the loop
        except asyncio.TimeoutError:
            await ctx.send("You took too long to respond. Game over!", delete_after=5)
            mines_game['game_over'] = True
            active_games.pop(user_id, None)
            break

# END OF MINES GAME
# Command list
@bot.command(aliases=['cmds'])
async def commands(ctx):
    embed = discord.Embed(title="Commands", description="List of available commands")
    embed.add_field(name="-blackjack <bet>", value="Start a new Blackjack game with the specified bet amount.", inline=False)
    embed.add_field(name="-hourly", value="Claim your hourly reward. (Once per hour)", inline=False)
    embed.add_field(name="-daily", value="Claim your daily reward. (Once per day)", inline=False)
    embed.add_field(name="-balance", value="Check your current balance.", inline=False)
    embed.add_field(name="-give ``recipient`` ``amount``", value="Give a specified amount to another user.", inline=False)
    embed.add_field(name="-baladd <amount>", value="Add a specified amount to your balance. (Admin use)", inline=False)
    embed.add_field(name="-leaderboard", value="Display the top 10 players on the leaderboard.", inline=False)
    embed.add_field(name="-grt <route_number> <stop_name>", value="Get the next arrival times for a GRT bus at a specific stop.", inline=False)
    await ctx.send(embed=embed) 

# Run the bot
bot.run("KEY") # Removed for security
