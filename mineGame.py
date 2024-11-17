import random

class Mines:
    def init_grid(self, grid_size, mine_ct):
        # Create grid 
        grid = [['Safe' for i in range(grid_size)] for i in range(grid_size)]
        all_pos = [(row, col) for row in range(grid_size) for col in range(grid_size)]

        # Select mine positions
        mine_pos = random.sample(all_pos, mine_ct)
        for row, col in mine_pos:
            grid[row][col] = 'Mine'
        return grid, mine_pos

    # Updated payout multiplier calculation
    def mult_calc(self, gems_revealed, mine_ct, grid_size):
        total_tiles = grid_size * grid_size
        total_mines = mine_ct
        total_safe_tiles = total_tiles - total_mines

        cumulative_multiplier = 1.0
        for s in range(1, gems_revealed + 1):
            remaining_total = total_tiles - (s - 1)
            remaining_safe = total_safe_tiles - (s - 1)
            per_pick_multiplier = remaining_total / remaining_safe
            cumulative_multiplier *= per_pick_multiplier

        # Apply house edge (e.g., 4% house edge)
        house_edge = 0.96  # You can adjust this value
        payout_multiplier = cumulative_multiplier * house_edge

        return payout_multiplier

    def play_game(self, grid_size, mine_ct):
        grid, mine_pos = self.init_grid(grid_size, mine_ct)
        revealed_pos = set()
        gems_revealed = 0
        game_over = False

        print(f"{mine_ct} mines hidden in the {grid_size}x{grid_size} grid.")

        while not game_over:
            self.display(grid, revealed_pos)

            row = int(input("Enter row: "))
            col = int(input("Enter column: "))

            if (row, col) in revealed_pos:
                print("Position already revealed. Try again.")
                continue

            if grid[row][col] == 'Mine':
                print("Boom! Game Over.")
                game_over = True
            else:
                revealed_pos.add((row, col))
                gems_revealed += 1
                multiplier = self.mult_calc(gems_revealed, mine_ct, grid_size)
                print(f"Found a gem! Multiplier: {multiplier:.2f}")

                withdraw = input("Do you want to withdraw? (y/n): ").lower()
                if withdraw == 'y' or withdraw == 'yes':
                    payout = multiplier * gems_revealed
                    print(f"Congratulations! You won {payout:.2f} gems.")
                    game_over = True

    def display(self, grid, revealed_pos):
        for row in range(len(grid)):
            row_display = []
            for col in range(len(grid[row])):
                if (row, col) in revealed_pos:
                    row_display.append('G')
                else:
                    row_display.append('X')
            print(' '.join(row_display))

    def display_discord_grid(self, grid, revealed_positions, game_over=False):
        display = ""
        for row in range(len(grid)):
            for col in range(len(grid[row])):
                if (row, col) in revealed_positions:
                    if grid[row][col] == 'Mine' and game_over:
                        display += '💣'  # Bomb emoji for hit mine
                    else:
                        display += '💎'  # Gem emoji for revealed
                else:
                    display += '🌫️'  # Black square for unrevealed
            display += '\n'
        return display