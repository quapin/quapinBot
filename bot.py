import discord
from discord.ext import commands
import asyncio
import sqlite3

# Create the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='+', intents=intents)

# Connect to the sqlite3 database
connection = sqlite3.connect('tictactoe.db')
conn = connection.cursor()



class TicTacToe:
    def __init__(self, player1, player2):
        self.board = [" "] * 9
        self.current_turn = player1
        self.player1 = player1
        self.player2 = player2
        self.game_over = False

    def print_board(self):
        return(
        f"```{self.board[0]} | {self.board[1]} | {self.board[2]}\n"
        f"---------\n"
        f"{self.board[3]} | {self.board[4]} | {self.board[5]}\n"
        f"---------\n"
        f"{self.board[6]} | {self.board[7]} | {self.board[8]}```"
        )
    
    def make_move(self, pos):
        if self.board[pos] == " ":
            if self.current_turn == self.player1:
                self.board[pos] = "X"
            else:
                self.board[pos] = "O"

            if self.is_winner():
                self.game_over = True
                return f"{self.current_turn.mention} wins!"
            # End in tie if no empty spaces and game is not over
            elif " " not in self.board:
                self.game_over = True
                return "Tie game!"
            
            self.current_turn = self.player2 if self.current_turn == self.player1 else self.player1
            return None
        else:
            return "Invalid position. Please choose an empty space (0 - 9)"


    def is_winner(self):
        # All possible indexes for winning
        win_combos = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8], # Horizontal
            [0, 3, 6], [1, 4, 7], [2, 5, 8], # Vertical
            [0, 4, 8], [2, 4, 6] # Diagonal
        ]
        for combo in win_combos:
            if self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]] != " ":
                self.game_over = True
                return True

        # Check if player 1 wins
        if self.current_turn == self.player1 and self.game_over == True:
            return True


        # Check if player 2 wins
        return False
        
ongoing_games = {}

@bot.command()
# Asynchronous method for running the Tic-Tac-Toe game
async def tictactoe(ctx, player2: discord.Member):
    # Edge cases and error handling
    if player2 is None:
        await ctx.send("Please mention a user to play against.")
        return
    if ctx.author == player2:
        await ctx.send("You cannot play against yourself.")
        return

    if ctx.author.id in ongoing_games:
        await ctx.send("Please finish your current game before starting a new one.")
        return

    if player2.id in ongoing_games:
        await ctx.send(f"`{player2.id}` is already in a game.")
        return
    
    ongoing_games[ctx.author.id] = TicTacToe(ctx.author, player2)
    await ctx.send(f"TicTacToe game started between `{ctx.author.id}` and `{player2.id}`.")
    await ctx.send(f"`{ongoing_games[ctx.author.id].current_turn}`'s turn.")

    play = ongoing_games[ctx.author.id]

    while not play.game_over:
        def check(m):
            return m.author == play.current_turn and m.channel == ctx.channel
        
        # Create countdown message
        countdown_message = await ctx.send(f"You have 15 seconds to make your move.\n{play.print_board()}")

        # Start countdown timer
        async def countdown():
            for i in range(14, 0, -1):
                # Update countdown message every second
                await asyncio.sleep(1)
                await countdown_message.edit(content=f"You have {i} seconds to make your move.\n{play.print_board()}")

        # Run countdown timer in the background
        countdown_task = asyncio.create_task(countdown())

        try:
            # Game timeout, and automatic win for opponent after 15s.
            msg = await bot.wait_for('message', timeout=15.0, check=check)
            # Cancel the countdown since player has made a move
            countdown_task.cancel()
            try:
                await countdown_task
            except asyncio.CancelledError:
                pass

            try:
                # Check if message is an integer and in range of board positions.
                position = int(msg.content)
                if position < 0 or position > 8:
                    await ctx.send("Please choose a position between 0 and 8.")
                    continue
            except ValueError:
                await ctx.send("Please enter a number. (0 - 8)")
                continue

            result = play.make_move(position)
            if result == "Invalid position. Please choose an empty space (0 - 8)":
                await ctx.send(result)
                continue

            await ctx.send(play.print_board())

            if result:
                await ctx.send(result)
                break
            else:
                await ctx.send(f"`{play.current_turn}`'s turn.")
                
        except asyncio.TimeoutError:
            # Cancel the countdown task since time is up
            countdown_task.cancel()
            try:
                await countdown_task
            except asyncio.CancelledError:
                pass
            opponent = play.player1 if play.current_turn == play.player2 else play.player2
            await ctx.send(f"Game over. `{opponent}` wins.")
            add_win(opponent)
            break

    # Remove the game from ongoing 
    del ongoing_games[ctx.author.id]

# Adds win to player in database
def add_win(player):
    # Initialize user with 1 win if they don't exist
    conn.execute("INSERT OR IGNORE INTO tictactoe (player, wins) VALUES (?, 0)", (player,))
    # Increment existing user win count by 1
    conn.execute("UPDATE tictactoe SET wins = wins + 1 WHERE player = ?", (player,))
    connection.commit()

# For debugging, remove from ongoing games
@bot.command()
async def endgame(ctx):
    if ctx.author.id in ongoing_games:
        del ongoing_games[ctx.author.id]
        await ctx.send("Game ended.")
    else:
        await ctx.send("There is no game to end.")

@bot.command()
# Show stats of selected user, if no user is selected, show stats of current user
async def stats(ctx, player: discord.Member = None):
    if player is None:
        player = ctx.author
    conn.execute("INSERT OR IGNORE INTO tictactoe (player, wins) VALUES (?, 0)", (player,))
    conn.execute("SELECT wins FROM tictactoe WHERE player = ?", (player,))
    wins = conn.fetchone()[0]
    await ctx.send(f"{player.mention} has {wins} wins.")


# Commands list
@bot.command()
async def commands(ctx):
    await ctx.send("```+tictactoe <@user> - Start a game of Tic-Tac-Toe with a user.```")
    await ctx.send("```+endgame - End the current game.```")
    await ctx.send("```+stats <@user> - Show the stats of a user.```")
    await ctx.send("```+commands - Show this list of commands.```")


# Start and run the bot
bot.run('MTI5NzY2Njg3OTU4MTU4NTUzMQ.Gsz7_N.eCmmFEOf1krCyujArSYW4BLcMkNx6KIih43bB0')
