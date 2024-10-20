import discord
from discord.ext import commands
import asynchio
import sqlite3

# Create the bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='+', intents=intents)

# Connect to the sqlite3 database
connection = sqlite3.connect('tictactoe.db')
conn = connection.cursor()

# Add wins into database, if player doesent exist, create player and add 1 to wins, else increment by 1.
#def add_win(player):

class TicTacToe:
    def __init__(self, player1, player2):
        self.board = [" "] * 9
        self.current_turn = player1
        self.player1 = player1
        self.player2 = player2
        self.game_over = False

        def board(self):
            return(
                f"{self.board[0]} | {self.board[1]} | {self.board[2]}\n"
                f"--|---|--|\n"
                f"{self.board[3]} | {self.board[4]} | {self.board[5]}\n"
                f"--|---|--|\n"
                f"{self.board[6]} | {self.board[7]} | {self.board[8]}\n"
            )
        
        def make_move(self, pos):
            if self.board[pos] == " ":
                if self.current_turn == self.player1:
                # Check if player 1 wins, end game if true
                    if self.is_winner():
                        print("Player 1 wins!")
                        return

                    self.board[pos] = "X"
                    self.current_turn = self.player2
                elif self.current_turn == self.player2:
                    self.board[pos] = "O"
                    if self.is_winner():
                        # Check if player 2 wins, end game if true
                        print("Player 2 wins!")
                        return
                    self.current_turn = self.player1

                # If no available spaces, and not a winner, end in a tie.

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


            # Check if player 2 wins
            return False
        
ongoing_games = {}

#@bot.command()
# Asynchronous method for running the Tic-Tac-Toe game
async def tictactoe(ctx, player2: discord.Member):
    # 
    if ctx.author == player2:
        await ctx.send("Select a user to play against.")
        return

    if ctx.author.id in ongoing_games:
        await ctx.send("Please finish your current game before starting a new one.")
        return

    if player2.id in ongoing_games:
        await ctx.send(f"`<@{player2.id}` is already in a game.")
        return
    
    ongoing_games[ctx.author.id] = TicTacToe(ctx.author, player2)
    await ctx.send(f"TicTacToe game started between `<@{ctx.author.id}>` and `<@{player2.id}>`.\n{ongoing_games[ctx.author.id].board()}")
    await ctx.send(f"{ongoing_games[ctx.author.id].current_turn}'s turn.")

    play = ongoing_games[ctx.author.id]

    while play.game_over != False:
        def check(m):
            return m.author == play.current_turn and m.channel == ctx.channel

        # Game timeout, and automatic win for opponent after 60s.
        try:
            # Game timeout, and automatic win for opponent after 60s.
            msg = await bot.wait_for('message', timeout=60.0, check=check)
            try:
                # Check if message is an integer and in range of board positions.
                position = int(msg.content)
                if position < 0 or position > 8:
                    await ctx.send("Please choose a position between 0 and 8.")
                    continue
            except ValueError:
                await ctx.send("Please enter a number.")
                continue

            result = play.make_move(position)
            await ctx.send(play.board())
            if result == True:
                await ctx.send(result)
                break

            await ctx.send(f"{play.current_turn.mention}'s turn.")
        except asynchio.TimeoutError:
            opponent = play.player1 if play.current_turn == play.player2 else play.player2
            await ctx.send(f"Game over. <@{opponent.id}> wins.")
            #add_win(opponent)
            break

def add_win(player):
    # Adds win to player in database
    conn.execute("INSERT INTO tictactoe (player, wins) VALUES (?, 1) ON CONFLICT(player) DO UPDATE SET wins = wins + 1", (player,))
    connection.commit()






