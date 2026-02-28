import os
import csv
import re
import random
import tkinter as tk
import sys
import traceback
import datetime
from tkinter import filedialog, simpledialog, messagebox, Checkbutton, IntVar


def detect_file_encoding(file_path):
    """
    Detect if a file is UTF-16-LE or UTF-8 encoded.
    Returns the encoding string to use with open().
    """
    try:
        with open(file_path, 'rb') as f:
            # Read first few bytes
            header = f.read(4)
            
            # Check for UTF-16-LE BOM (FF FE)
            if header[:2] == b'\xff\xfe':
                return 'utf-16-le'
            
            # Check for null bytes pattern typical of UTF-16-LE (every other byte is null)
            # Read more of the file to check
            f.seek(0)
            sample = f.read(100)
            
            # Count null bytes - UTF-16-LE has many null bytes
            null_count = sample.count(b'\x00')
            
            # If roughly half the bytes are nulls, it's likely UTF-16-LE
            if len(sample) > 0 and null_count > len(sample) * 0.3:
                return 'utf-16-le'
            
            # Default to UTF-8
            return 'utf-8'
    except Exception as e:
        print(f"Warning: Could not detect encoding for {file_path}: {e}")
        return 'utf-8'  # Default fallback


class TeamAppender:
    def __init__(self, team_name, team_id, league_id, nation_id=None, is_national_team=False, stadium_id=None):
        """
        Initialize TeamAppender with the new team information

        Args:
            team_name (str): The name of the new team
            team_id (int): The ID to assign to the new team
            league_id (int): The league ID to assign to the team
            nation_id (int, optional): The nation ID for national teams
            is_national_team (bool): Whether this is a national team
            stadium_id (int, optional): The stadium ID to link to the team
        """
        self.team_name = team_name
        self.team_id = team_id
        self.league_id = league_id
        self.nation_id = nation_id
        self.is_national_team = is_national_team
        self.stadium_id = stadium_id
        self.players = []
        self.goalkeepers = []
        self.starting_eleven = []
        self.captain_id = None
        self.player_ids = None  # Added to store player IDs consistently

        # Dictionary to store file headers and column positions
        self.file_headers = {}

        # Define standard positions for sorting and selection
        self.position_order = {
            'GK': 0,  # Goalkeeper
            'CB': 1,  # Central Defender
            'RB': 2,  # Right Back
            'LB': 3,  # Left Back
            'CDM': 4,  # Defensive Midfielder
            'CM': 5,  # Central Midfielder
            'CAM': 6,  # Attacking Midfielder
            'RM': 7,  # Right Midfielder/Winger
            'LM': 8,  # Left Midfielder/Winger
            'ST': 9,  # Striker
            'CF': 10  # Center Forward
        }

        # Formation positions (4-3-3 with GK)
        self.formation_positions = [
            'GK',  # Goalkeeper
            'CB', 'CB',  # Center Backs
            'LB', 'RB',  # Full Backs
            'CDM',  # Defensive Midfielder
            'CM', 'CM',  # Central Midfielders
            'LM', 'RM',  # Wingers
            'ST'  # Striker
        ]

    def load_player_data(self, player_file_path):
        """
        Load player data from the CSV/TXT file

        Args:
            player_file_path (str): Path to the player CSV/TXT file
        """
        print(f"Loading player data from: {player_file_path}")

        # Handle national team player loading from players.txt
        if self.is_national_team:
            return self.load_national_team_players(player_file_path)

        # Regular club team player loading
        try:
            with open(player_file_path, 'r', encoding='utf-8') as file:
                # Use tab as the delimiter
                reader = csv.DictReader(file, delimiter='\t')
                for row in reader:
                    try:
                        row['playerid'] = int(row['playerid'])
                        row['ovr'] = int(row['ovr'])

                        # Store position information
                        pos1 = row.get('pos1', '')
                        pos2 = row.get('pos2', '')
                        pos3 = row.get('pos3', '')

                        # Add position order for sorting
                        row['pos_order'] = self.position_order.get(pos1, 999)

                        # Store all positions for this player
                        row['positions'] = [pos for pos in [pos1, pos2, pos3] if pos]

                        # Separate goalkeepers from field players but include both
                        if pos1 == 'GK':
                            self.goalkeepers.append(row)
                        else:
                            self.players.append(row)
                    except (ValueError, KeyError) as e:
                        print(
                            f"Warning: Skipped player with invalid data: {row.get('given', 'Unknown')} {row.get('sur', 'Unknown')} - {str(e)}")

            if not self.players:
                print("Error: No valid field players found in the file.")
                return False

            # Create a balanced squad based on positions
            self.create_balanced_squad()

            # Initialize the consistent player IDs list after creating the squad
            self.player_ids = self.get_starting_player_ids()

            print(
                f"Loaded {len(self.players)} field players and {len(self.goalkeepers)} goalkeepers. Captain ID: {self.captain_id}")
            return True

        except Exception as e:
            print(f"Error loading player file: {e}")
            return False

    def load_national_team_players(self, players_file_path):
        """
        Load national team players from the players.txt file
        Filters by nationality, gender, and positions
        Excludes blacklisted players

        Args:
            players_file_path (str): Path to the players.txt file
        """
        print(f"Loading players for nation ID {self.nation_id} from: {players_file_path}")

        # Load blacklisted player IDs
        blacklisted_players = load_blacklisted_players()

        try:
            with open(players_file_path, 'r', encoding='utf-16-le') as file:
                # Read header line to determine column indices
                header_line = file.readline().strip()
                headers = header_line.split('\t')

                # Create mapping of column names to indices
                column_indices = {col.lower(): idx for idx, col in enumerate(headers)}

                # Check for required columns
                required_columns = ['playerid', 'nationality', 'gender', 'preferredposition1', 'overallrating']
                for col in required_columns:
                    if col not in column_indices:
                        print(f"Error: Required column '{col}' not found in players.txt header.")
                        return False

                # Process player rows
                for line in file:
                    fields = line.strip().split('\t')

                    # Skip rows that don't have enough fields
                    if len(fields) <= max(column_indices.values()):
                        continue

                    try:
                        # Extract key fields
                        player_id = int(fields[column_indices['playerid']])

                        # Skip blacklisted players
                        if player_id in blacklisted_players:
                            continue

                        nationality = int(fields[column_indices['nationality']])
                        gender = int(fields[column_indices['gender']])
                        position1 = fields[column_indices['preferredposition1']]
                        overall = int(fields[column_indices['overallrating']])

                        # Match nationality and gender
                        if nationality == self.nation_id and gender == 0:
                            # Create a dict with player data
                            player_data = {
                                'playerid': player_id,
                                'ovr': overall,
                                'pos1': self.map_game_position_to_standard(position1),
                                'given': 'Player',  # We don't have names, so using placeholders
                                'sur': str(player_id)
                            }

                            # Add position order for sorting
                            player_data['pos_order'] = self.position_order.get(player_data['pos1'], 999)

                            # Store all positions for this player (just the primary one in this case)
                            player_data['positions'] = [player_data['pos1']]

                            # Separate goalkeepers from field players
                            if player_data['pos1'] == 'GK':
                                self.goalkeepers.append(player_data)
                            else:
                                self.players.append(player_data)

                    except (ValueError, IndexError) as e:
                        # Silently skip invalid rows
                        continue

            # Check if we found enough players
            if not self.players:
                print(f"Error: No valid field players found for nation ID {self.nation_id}")
                return False

            print(
                f"Found {len(self.players)} field players and {len(self.goalkeepers)} goalkeepers for nation ID {self.nation_id}")

            # Create a balanced squad based on positions
            self.create_balanced_squad()

            # Initialize the player IDs list
            self.player_ids = self.get_starting_player_ids()

            print(f"Created squad with captain ID: {self.captain_id}")
            return True

        except Exception as e:
            print(f"Error loading national team players: {e}")
            traceback.print_exc()
            return False

    def map_game_position_to_standard(self, game_position):
        """Map FIFA game position ID to standard position code"""
        # Position mapping based on FIFA position codes
        position_map = {
            "0": "GK",  # Goalkeeper
            "1": "SW",  # Sweeper
            "3": "RB",  # Right Back
            "4": "RCB",  # Right Center Back
            "5": "CB",  # Center Back
            "6": "LCB",  # Left Center Back
            "7": "LB",  # Left Back
            "9": "RDM",  # Right Defensive Mid
            "10": "CDM",  # Center Defensive Mid
            "11": "LDM",  # Left Defensive Mid
            "12": "RM",  # Right Midfielder
            "13": "RCM",  # Right Center Mid
            "14": "CM",  # Center Mid
            "15": "LCM",  # Left Center Mid
            "16": "LM",  # Left Midfielder
            "17": "RAM",  # Right Attacking Mid
            "18": "CAM",  # Center Attacking Mid
            "19": "LAM",  # Left Attacking Mid
            "20": "RF",  # Right Forward
            "22": "LF",  # Left Forward
            "23": "RW",  # Right Wing
            "24": "RS",  # Right Striker
            "25": "ST",  # Striker
            "26": "LS",  # Left Striker
            "27": "LW",  # Left Wing
        }


        # Map to standard positions or return default
        return position_map.get(game_position, "CM")  # Default to CM if unknown

    def create_balanced_squad(self):
        """
        Create a properly balanced squad, considering both position match AND overall rating.
        A high-overall player in a compatible position can beat a low-overall natural position player.
        """
        # Define the formation slots with their acceptable positions (in priority order)
        # Format: index, name, game_id, [list of acceptable pos1 values in priority order]
        formation_slots = [
            (0, "GK", "0", ["GK"]),
            (1, "RB", "3", ["RB", "RWB", "CB"]),
            (2, "RCB", "4", ["CB"]),
            (3, "LCB", "6", ["CB"]),
            (4, "LB", "7", ["LB", "LWB", "CB"]),
            (5, "CDM", "10", ["CDM", "CM", "CAM"]),
            (6, "RCM", "13", ["CM", "CDM", "CAM"]),
            (7, "LCM", "15", ["CM", "CDM", "CAM"]),
            (8, "RW", "23", ["RW", "RM", "ST", "CAM"]),
            (9, "ST", "25", ["ST", "CF", "RW", "LW"]),
            (10, "LW", "27", ["LW", "LM", "ST", "CAM"]),
        ]

        # Position penalty - how many OVR points to subtract for each position tier away from primary
        # e.g., if penalty=3: an 85 OVR RM scores 82 for RW slot (85 - 1*3), beating a 70 OVR RW (70 - 0*3)
        POSITION_PENALTY = 3

        # Initialize empty squad
        self.starting_eleven = [None] * 11
        used_players = set()

        # Combine all players (GKs separate for safety)
        all_gks = sorted(self.goalkeepers, key=lambda x: x.get('ovr', 0), reverse=True)
        all_field = sorted(self.players, key=lambda x: x.get('ovr', 0), reverse=True)

        print("\n=== BUILDING STARTING XI ===")
        print(f"Available: {len(all_gks)} GKs, {len(all_field)} field players")
        print(f"Position penalty: {POSITION_PENALTY} OVR per position tier")

        # Count players by position
        pos_counts = {}
        for p in all_field:
            pos = p.get('pos1', 'Unknown')
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        print(f"Position breakdown: {pos_counts}")

        # PASS 1: Fill each slot considering both position AND overall
        print("\nPASS 1: Assigning best players (position + overall)")
        for idx, name, game_id, acceptable_positions in formation_slots:
            if self.starting_eleven[idx] is not None:
                continue

            # Special handling for GK - only use goalkeepers
            if name == "GK":
                available = [p for p in all_gks if p['playerid'] not in used_players]
                if available:
                    player = available[0]
                    self.starting_eleven[idx] = player
                    used_players.add(player['playerid'])
                    print(f"  [{idx}] {name}: {player.get('given', '')} {player.get('sur', '')} ({player.get('pos1')}, OVR {player.get('ovr')})")
                continue

            # For field positions, find the best player considering position priority AND overall
            best_candidate = None
            best_score = -999
            best_info = ""

            for priority, acc_pos in enumerate(acceptable_positions):
                for player in all_field:
                    if player['playerid'] in used_players:
                        continue
                    if player.get('pos1') == acc_pos:
                        # Calculate score: overall minus position penalty
                        ovr = player.get('ovr', 0)
                        score = ovr - (priority * POSITION_PENALTY)
                        
                        if score > best_score:
                            best_score = score
                            best_candidate = player
                            if priority == 0:
                                best_info = f"natural {acc_pos}"
                            else:
                                best_info = f"{acc_pos}→{name}, penalty -{priority * POSITION_PENALTY}"

            if best_candidate:
                self.starting_eleven[idx] = best_candidate
                used_players.add(best_candidate['playerid'])
                print(f"  [{idx}] {name}: {best_candidate.get('given', '')} {best_candidate.get('sur', '')} ({best_candidate.get('pos1')}, OVR {best_candidate.get('ovr')}) [{best_info}]")

        # PASS 2: Fill any remaining slots with best available players by position group
        print("\nPASS 2: Filling remaining slots with compatible players")
        defense_pos = ["CB", "RB", "LB", "RWB", "LWB"]
        midfield_pos = ["CDM", "CM", "CAM", "RM", "LM"]
        attack_pos = ["ST", "CF", "RW", "LW"]

        for idx, name, game_id, acceptable_positions in formation_slots:
            if self.starting_eleven[idx] is not None:
                continue

            if name == "GK":
                continue  # Already handled

            # Determine position group
            if name in ["RB", "RCB", "LCB", "LB"]:
                search_order = defense_pos + midfield_pos
            elif name in ["CDM", "RCM", "LCM"]:
                search_order = midfield_pos + defense_pos + attack_pos
            else:  # RW, ST, LW
                search_order = attack_pos + midfield_pos

            assigned = False
            for search_pos in search_order:
                if assigned:
                    break
                for player in all_field:
                    if player['playerid'] in used_players:
                        continue
                    if player.get('pos1') == search_pos:
                        self.starting_eleven[idx] = player
                        used_players.add(player['playerid'])
                        print(f"  [{idx}] {name}: {player.get('given', '')} {player.get('sur', '')} ({player.get('pos1')}, OVR {player.get('ovr')}) [backup]")
                        assigned = True
                        break

        # PASS 3: Last resort - fill with any remaining player
        print("\nPASS 3: Last resort fill")
        for idx, name, game_id, acceptable_positions in formation_slots:
            if self.starting_eleven[idx] is not None:
                continue

            if name == "GK":
                available = [p for p in all_gks if p['playerid'] not in used_players]
            else:
                available = [p for p in all_field if p['playerid'] not in used_players]

            if available:
                player = available[0]
                self.starting_eleven[idx] = player
                used_players.add(player['playerid'])
                print(f"  [{idx}] {name}: {player.get('given', '')} {player.get('sur', '')} ({player.get('pos1')}, OVR {player.get('ovr')}) [last resort]")

        # Set captain as highest-rated outfield player
        field_players = [p for p in self.starting_eleven if p and p.get('pos1') != 'GK']
        if field_players:
            captain = max(field_players, key=lambda x: x.get('ovr', 0))
            self.captain_id = captain['playerid']
        else:
            self.captain_id = self.starting_eleven[0]['playerid'] if self.starting_eleven[0] else None

        # Print final squad
        print("\n=== FINAL STARTING XI ===")
        for idx, name, game_id, _ in formation_slots:
            player = self.starting_eleven[idx]
            if player:
                is_captain = " (C)" if player['playerid'] == self.captain_id else ""
                print(f"  {idx}. {name} (pos_id={game_id}): {player.get('given', '')} {player.get('sur', '')} - {player.get('pos1')} - OVR {player.get('ovr')}{is_captain}")
            else:
                print(f"  {idx}. {name} (pos_id={game_id}): EMPTY!")

        # Store game position IDs for other methods
        self.game_position_ids = [slot[2] for slot in formation_slots]

        return True

    def append_to_teamplayerlinks_file(self, file_path):
        """Append team player links with the exact game position IDs and remove any links to team 111592"""
        try:
            if os.path.exists(file_path):
                # Auto-detect file encoding
                file_encoding = detect_file_encoding(file_path)
                
                # Parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "teamplayerlinks")

                # Get the positions of important columns
                artificial_key_idx = header_dict.get("artificialkey", 6)  # Default to 6 if not found
                teamid_idx = header_dict.get("teamid", 7)  # Default to 7 if not found
                playerid_idx = header_dict.get("playerid", 13)  # Default to 13 if not found

                # Get the next artificial key from the correct column
                if artificial_key_idx is not None:
                    next_key = self.get_highest_id_from_file(file_path, artificial_key_idx, 26271) + 1
                    print(f"Found artificialkey at column {artificial_key_idx}, next key: {next_key}")
                else:
                    next_key = 26272
                    print(f"Could not find artificialkey column, using default: {next_key}")

                # For club teams, identify players linked to team 111592
                players_to_remove_from_111592 = {}
                if not self.is_national_team:
                    print("Checking for players linked to team ID 111592...")
                    try:
                        # Keep track of the player IDs we'll be using in our team
                        our_player_ids = set()
                        for player in self.starting_eleven:
                            if player:
                                our_player_ids.add(str(player['playerid']))
                        for player in self.goalkeepers + self.players:
                            our_player_ids.add(str(player['playerid']))

                        print(f"Our team will use {len(our_player_ids)} players")

                        # Process the file to find lines where our players are linked to team 111592
                        with open(file_path, 'r', encoding=file_encoding) as file:
                            lines = file.readlines()

                        # Store the file content and lines to remove
                        file_content = []
                        lines_to_remove = []

                        for i, line in enumerate(lines):
                            parts = line.strip().split('\t')
                            if len(parts) > max(teamid_idx, playerid_idx):
                                try:
                                    team_id = parts[teamid_idx]
                                    player_id = parts[playerid_idx]

                                    # Check if this player is in our team AND currently linked to team 111592
                                    if team_id == "111592" and player_id in our_player_ids:
                                        lines_to_remove.append(i)
                                        players_to_remove_from_111592[player_id] = i
                                        print(f"Will remove player ID {player_id} from team 111592")

                                    # Keep the line
                                    file_content.append(line)
                                except (ValueError, IndexError):
                                    file_content.append(line)
                            else:
                                file_content.append(line)

                        # Remove the identified lines
                        if lines_to_remove:
                            print(f"Removing {len(lines_to_remove)} links to team 111592")
                            for index in sorted(lines_to_remove, reverse=True):
                                del file_content[index]

                        # Write the modified content back
                        with open(file_path, 'w', encoding=file_encoding) as file:
                            file.writelines(file_content)

                        print(f"Removed {len(players_to_remove_from_111592)} player links from team 111592")

                    except Exception as e:
                        print(f"Warning: Could not scan or remove players linked to 111592: {str(e)}")
                        traceback.print_exc()  # Print the full error trace

                # Use the exact game position IDs stored during create_balanced_squad
                if hasattr(self, 'game_position_ids'):
                    starting_position_ids = self.game_position_ids
                else:
                    # Fallback to the exact position IDs provided by user if method is called directly
                    starting_position_ids = ["0", "3", "4", "6", "7", "10", "13", "15", "23", "25", "27"]

                # Count the total number of available players (both starting and non-starting)
                total_available_players = len(self.starting_eleven) + len([p for p in self.goalkeepers + self.players
                                                                           if p not in self.starting_eleven])

                print(f"Total available players in data file: {total_available_players}")

                # Calculate how many additional players we need to add after the starting 11
                additional_players_count = total_available_players - len(self.starting_eleven)

                # Determine position IDs for remaining players
                # For national teams vs club teams
                if self.is_national_team:
                    # For national teams, all additional players are reserves (28)
                    sub_position_ids = ["28"] * additional_players_count
                else:
                    # For club teams, first 7 are subs (28), rest are reserves (29)
                    sub_count = min(7, additional_players_count)
                    reserve_count = additional_players_count - sub_count
                    sub_position_ids = ["28"] * sub_count + ["29"] * reserve_count

                # Combine all position IDs - only as many as we have actual players
                position_ids = starting_position_ids + sub_position_ids

                # Make sure we don't have more position IDs than actual players
                position_ids = position_ids[:total_available_players]

                # Print confirmation of position ID mapping for debugging
                print("\nTEAMPLAYERLINKS POSITION MAPPING:")
                for i in range(min(11, len(starting_position_ids))):
                    player = self.starting_eleven[i] if i < len(self.starting_eleven) else None
                    player_name = f"{player.get('given', '')} {player.get('sur', '')}" if player else "Unknown"
                    print(f"Position {i}: ID {starting_position_ids[i]} - {player_name}")

                teamplayerlinks_lines = []

                # Collect all players (starting eleven plus additional players)
                all_players = self.starting_eleven.copy()

                # First get the player IDs already in starting lineup
                starting_player_ids = [p['playerid'] for p in self.starting_eleven if p]

                # Need to ensure a better position distribution for subs/reserves
                # Only need 1 backup GK for national teams
                backup_gks = []
                for player in self.goalkeepers:
                    if player['playerid'] not in starting_player_ids:
                        backup_gks.append(player)

                # Sort by overall rating
                backup_gks.sort(key=lambda x: x.get('ovr', 0), reverse=True)

                # Get outfield players (non-GKs)
                outfield_players = []
                for player in self.players:
                    if player['playerid'] not in starting_player_ids:
                        outfield_players.append(player)

                # Sort by overall rating
                outfield_players.sort(key=lambda x: x.get('ovr', 0), reverse=True)

                # Handle players differently based on team type
                additional_players = []

                if self.is_national_team:
                    # NATIONAL TEAMS: Add just 1 backup goalkeeper
                    if backup_gks:
                        additional_players.append(backup_gks[0])

                    # Add outfield players
                    additional_players.extend(outfield_players)
                else:
                    # CLUB TEAMS: Add ALL backup GKs
                    additional_players.extend(backup_gks)

                    # Add outfield players
                    additional_players.extend(outfield_players)

                # Add the additional players to all_players
                all_players.extend(additional_players)

                # Limit national team to 26 players with balanced positions
                if self.is_national_team:
                    max_squad_size = 26
                    if len(all_players) > max_squad_size:
                        print(f"Limiting national team from {len(all_players)} to {max_squad_size} players")

                        # Keep starting XI
                        limited_squad = all_players[:11]

                        # Add 1 backup GK
                        remaining_gks = [p for p in all_players[11:] if p.get('pos1') == 'GK']
                        if remaining_gks:
                            limited_squad.append(remaining_gks[0])

                        # Fill rest with balanced outfield positions
                        remaining_spots = max_squad_size - len(limited_squad)
                        remaining_outfield = [p for p in all_players[11:] if p.get('pos1') != 'GK']

                        # Split by position type
                        defenders = [p for p in remaining_outfield if p.get('pos1') in ['CB', 'RB', 'LB', 'RWB', 'LWB']]
                        midfielders = [p for p in remaining_outfield if
                                       p.get('pos1') in ['CDM', 'CM', 'CAM', 'RM', 'LM']]
                        forwards = [p for p in remaining_outfield if p.get('pos1') in ['ST', 'CF', 'RW', 'LW']]

                        # Add roughly equal numbers of each position
                        def_count = min(len(defenders), remaining_spots // 3)
                        mid_count = min(len(midfielders), remaining_spots // 3)
                        fwd_count = min(len(forwards), remaining_spots - def_count - mid_count)

                        limited_squad.extend(defenders[:def_count])
                        limited_squad.extend(midfielders[:mid_count])
                        limited_squad.extend(forwards[:fwd_count])

                        # If still under the limit, add best remaining players
                        remaining_spots = max_squad_size - len(limited_squad)
                        if remaining_spots > 0:
                            remaining_players = [p for p in all_players[11:] if p not in limited_squad]
                            remaining_players.sort(key=lambda x: x.get('ovr', 0), reverse=True)
                            limited_squad.extend(remaining_players[:remaining_spots])

                        all_players = limited_squad

                    # Store the limited squad for use in other methods
                    self.limited_squad = all_players

                print(f"Final squad size: {len(all_players)} players")

                # Ensure we don't have more players than actual data
                total_available_players = len(all_players)

                # Add all players with the specified position IDs
                for i, player in enumerate(all_players):
                    if i < len(position_ids):
                        position = position_ids[i]
                    else:
                        position = "29"  # Default for any additional players (unlikely to hit this case)

                    jersey_number = player.get('jersey', i + 1)  # Use jersey number from data if available

                    # Check if this player was removed from team 111592
                    player_id_str = str(player['playerid'])
                    if player_id_str in players_to_remove_from_111592:
                        print(
                            f"Player ID {player_id_str} was removed from team 111592 and is now exclusively in team {self.team_id}")

                    teamplayerlinks_lines.append(
                        f"0\t0\t0\t0\t{jersey_number}\t{position}\t{next_key + i}\t{self.team_id}\t0\t0\t0\t0\t0\t{player['playerid']}\t0\t0")

                # Join the links into a template
                teamplayerlinks_template = '\n'.join(teamplayerlinks_lines)

                # Read the existing content to keep it
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new links to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + teamplayerlinks_template)

                print(f"✓ Added team player links to file: {file_path}, linked {len(teamplayerlinks_lines)} players")

                if players_to_remove_from_111592:
                    print(
                        f"✓ Successfully removed {len(players_to_remove_from_111592)} players from team 111592 and added them to team {self.team_id}")

                return True
            else:
                print(f"✗ Teamplayerlinks file not found: {file_path}")
                return False

        except Exception as e:
            print(f"✗ Error appending to teamplayerlinks file: {str(e)}")
            traceback.print_exc()  # Print full traceback for debugging
            return False

    def append_to_team_nationlinks_file(self, file_path):
        """
        Append entry to the teamnationlinks.txt file for national teams
        Format: leagueid(78) teamid nationid

        Args:
            file_path (str): Path to the teamnationlinks.txt file
        """
        try:
            if not self.is_national_team or self.nation_id is None:
                print("Not a national team, skipping teamnationlinks.txt")
                return True

            if os.path.exists(file_path):
                # Auto-detect encoding
                file_encoding = detect_file_encoding(file_path)
                
                # Read the existing content
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Create the new link line (league 78 for national teams)
                nationlink_line = f"78\t{self.team_id}\t{self.nation_id}"

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new link and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + nationlink_line)

                print(f"✓ Added team-nation link to file: {file_path}")
                return True
            else:
                print(f"✗ Teamnationlinks file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to teamnationlinks file: {str(e)}")
            traceback.print_exc()
            return False

    def append_to_teamstadiumlinks_file(self, file_path):
        """
        Append entry to the teamstadiumlinks.txt file to link team with stadium
        Format: 0	stadium_id	team_id	0

        Args:
            file_path (str): Path to the teamstadiumlinks.txt file
        """
        try:
            if self.stadium_id is None:
                print("No stadium ID specified, skipping teamstadiumlinks.txt")
                return True

            if os.path.exists(file_path):
                # Auto-detect encoding
                file_encoding = detect_file_encoding(file_path)
                
                # Read the existing content
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Create the new link line: 0	stadium_id	team_id	0
                stadiumlink_line = f"0\t{self.stadium_id}\t{self.team_id}\t0"

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new link and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + stadiumlink_line)

                print(f"✓ Added team-stadium link to file: {file_path} (Stadium ID: {self.stadium_id})")
                return True
            else:
                print(f"✗ Teamstadiumlinks file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to teamstadiumlinks file: {str(e)}")
            traceback.print_exc()
            return False

    def parse_file_header(self, file_path, file_type):
        """
        Parse the header line of a file to understand its structure

        Args:
            file_path (str): Path to the file
            file_type (str): Type of file being parsed (for reference)

        Returns:
            dict: Dictionary mapping column names to their indices
        """
        try:
            # Auto-detect encoding
            file_encoding = detect_file_encoding(file_path)
            with open(file_path, 'r', encoding=file_encoding) as file:
                header_line = file.readline().strip()

            if not header_line:
                print(f"Warning: {file_type} file has no header line")
                return {}

            header_columns = header_line.split('\t')
            header_dict = {col: idx for idx, col in enumerate(header_columns)}

            print(f"Parsed header for {file_type}: Found {len(header_dict)} columns")
            self.file_headers[file_type] = header_dict  # Store the header mapping

            return header_dict
        except Exception as e:
            print(f"Error parsing header for {file_type} file: {str(e)}")
            return {}

    def get_highest_id_from_file(self, file_path, column_idx, default_value=0):
        """
        Get the highest numeric value from a specific column in a file

        Args:
            file_path (str): Path to the file
            column_idx (int): Index of the column to look at
            default_value (int): Default value to return if no values found

        Returns:
            int: Highest value found, or default if none found
        """
        try:
            # Auto-detect encoding
            file_encoding = detect_file_encoding(file_path)
            with open(file_path, 'r', encoding=file_encoding) as file:
                # Skip header
                next(file)

                # Process all other lines
                id_values = []
                for line in file:
                    parts = line.strip().split('\t')
                    if len(parts) > column_idx:
                        try:
                            id_val = parts[column_idx]
                            if id_val.isdigit():
                                id_values.append(int(id_val))
                        except (ValueError, IndexError):
                            pass

            if id_values:
                return max(id_values)

            return default_value

        except Exception as e:
            print(f"Error getting highest ID: {str(e)}")
            return default_value

    def append_to_formations_file(self, file_path, selected_formation=None):
        """Append formation to the formations.txt file"""
        try:
            if os.path.exists(file_path):
                # Parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "formations")

                # Get the next formation ID from the correct column
                formationid_idx = header_dict.get('formationid')
                if formationid_idx is not None:
                    next_formation_id = self.get_highest_id_from_file(file_path, formationid_idx, 1) + 1
                    print(f"Found formationid at column {formationid_idx}, next ID: {next_formation_id}")
                else:
                    next_formation_id = 2
                    print(f"Could not find formationid column, using default: {next_formation_id}")

                # Read the entire content to keep it (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # If user selected a specific formation, use that data
                if selected_formation:
                    # Build the formation template using the selected formation's data
                    formations_template = (
                        f"{selected_formation.get('offset6x', '0.65')}\t"
                        f"{selected_formation.get('offset5y', '0.3375')}\t"
                        f"{selected_formation.get('offset10x', '0.075')}\t"
                        f"{selected_formation.get('offset2x', '0.6731')}\t"
                        f"{selected_formation.get('defenders', '4')}\t"
                        f"{selected_formation.get('offset2y', '0.1537')}\t"
                        f"{selected_formation.get('offset6y', '0.5125')}\t"
                        f"{selected_formation.get('offset7x', '0.35')}\t"
                        f"{selected_formation.get('offset3x', '0.325')}\t"
                        f"{selected_formation.get('offset8x', '0.925')}\t"
                        f"{selected_formation.get('offset10y', '0.825')}\t"
                        f"{selected_formation.get('offset3y', '0.15')}\t"
                        f"{selected_formation.get('offset4x', '0.075')}\t"
                        f"{selected_formation.get('offset7y', '0.5125')}\t"
                        f"{selected_formation.get('offset0x', '0.497')}\t"
                        f"{selected_formation.get('offset8y', '0.825')}\t"
                        f"{selected_formation.get('attackers', '3')}\t"
                        f"{selected_formation.get('offset9x', '0.4995')}\t"
                        f"{selected_formation.get('midfielders', '3')}\t"
                        f"{selected_formation.get('offset5x', '0.5')}\t"
                        f"{selected_formation.get('offset0y', '0.0175')}\t"
                        f"{selected_formation.get('offset1x', '0.9')}\t"
                        f"{selected_formation.get('offset4y', '0.2')}\t"
                        f"{selected_formation.get('offset9y', '0.875')}\t"
                        f"{selected_formation.get('offset1y', '0.175')}\t"
                        f"{selected_formation.get('pos0role', '4161')}\t"
                        f"{selected_formation.get('pos6role', '21314')}\t"
                        f"{selected_formation.get('pos8role', '33794')}\t"
                        f"{selected_formation.get('pos4role', '8386')}\t"
                        f"{selected_formation.get('pos7role', '21314')}\t"
                        f"{selected_formation.get('pos2role', '12737')}\t"
                        f"{selected_formation.get('pos1role', '8386')}\t"
                        f"{selected_formation.get('pos10role', '33794')}\t"
                        f"{selected_formation.get('pos3role', '12737')}\t"
                        f"{selected_formation.get('pos9role', '12737')}\t"
                        f"{selected_formation.get('pos5role', '17089')}\t"
                        f"{selected_formation.get('name', '4-3-3')}\t"
                        f"{selected_formation.get('position10', '27')}\t"
                        f"{selected_formation.get('position6', '13')}\t"
                        f"{selected_formation.get('offensiverating', '3')}\t"
                        f"{selected_formation.get('position8', '23')}\t"
                        f"{selected_formation.get('position5', '10')}\t"
                        f"{selected_formation.get('audio_id', '6')}\t"
                        f"{self.team_id}\t"
                        f"{selected_formation.get('position2', '4')}\t"
                        f"{next_formation_id}\t"  # Always use auto-incremented ID
                        f"{selected_formation.get('relativeformationid', '9')}\t"
                        f"{selected_formation.get('position4', '7')}\t"
                        f"{selected_formation.get('position3', '6')}\t"
                        f"{selected_formation.get('fullname_id', '7')}\t"
                        f"{selected_formation.get('position0', '0')}\t"
                        f"{selected_formation.get('position9', '25')}\t"
                        f"{selected_formation.get('position7', '15')}\t"
                        f"{selected_formation.get('position1', '3')}"
                    )
                else:
                    # Template structure from the user's example with updated IDs
                    formations_template = f"""0.65\t0.3375\t0.075\t0.6731\t4\t0.1537\t0.5125\t0.35\t0.325\t0.925\t0.825\t0.15\t0.075\t0.5125\t0.497\t0.825\t3\t0.4995\t3\t0.5\t0.0175\t0.9\t0.2\t0.875\t0.175\t4161\t21314\t33794\t8386\t21314\t12737\t8386\t33794\t12737\t12737\t17089\t4-3-3\t27\t13\t3\t23\t10\t6\t{self.team_id}\t4\t{next_formation_id}\t9\t7\t6\t7\t0\t25\t15\t3"""

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new formation to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + formations_template)

                print(f"✓ Added formation to file: {file_path}")
                return True
            else:
                print(f"✗ Formations file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to formations file: {str(e)}")
            traceback.print_exc()
            return False

    def get_starting_player_ids(self):
        """Get the exact same player IDs to use across all files"""
        if self.player_ids is not None:
            return self.player_ids

        player_ids = []
        for player in self.starting_eleven[:11]:
            player_ids.append(player['playerid'])

        # Print for debugging
        print("\nPlayer IDs for starting eleven:")
        for i, pid in enumerate(player_ids):
            print(f"Position {i}: {pid}")
        print()

        return player_ids

    def append_to_teams_file(self, file_path):
        """Append a new team to the teams.txt file"""
        try:
            if os.path.exists(file_path):
                # First parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "teams")

                # Read the entire content to keep it (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # New header structure (110 columns):
                # assetid, teamcolor1g, teamcolor1r, clubworth, teamcolor2b, goalnetstanchioncolor2g,
                # teamcolor2r, foundationyear, goalnetstanchioncolor2r, teamcolor3r, goalnetstanchioncolor1b,
                # teamcolor1b, opponentweakthreshold, latitude, teamcolor3g, opponentstrongthreshold,
                # goalnetstanchioncolor2b, goalnetstanchioncolor1r, teamcolor2g, goalnetstanchioncolor1g,
                # teamname(20), teamcolor3b, presassetone, powid, hassubstitutionboard, rightfreekicktakerid(25),
                # flamethrowercannon, domesticprestige, genericint2, cksupport7, defensivedepth, hasvikingclap,
                # jerseytype, pitchcolor, cksupport9, pitchwear, popularity, hastifo, presassettwo,
                # teamstadiumcapacity, stadiumgoalnetstyle, iscompetitionscarfenabled, cityid, rivalteam,
                # playsurfacetype, isbannerenabled, midfieldrating, cksupport8, stadiummowpattern_code,
                # cksupport6, matchdayoverallrating, matchdaymidfieldrating, attackrating, longitude,
                # buildupplay, matchdaydefenserating, hasstandingcrowd, favoriteteamsheetid, defenserating,
                # iscompetitionpoleflagenabled, skinnyflags, uefa_consecutive_wins, longkicktakerid(62),
                # trait1vweak, iscompetitioncrowdcardsenabled, rightcornerkicktakerid(65), throwerleft, gender,
                # cksupport1, cornerflagpolecolor, uefa_cl_wins, hassuncanthem, domesticcups, ethnicity,
                # leftcornerkicktakerid(74), youthdevelopment, teamid(76), uefa_el_wins, trait1vequal,
                # numtransfersin, stanchionflamethrower, stadiumgoalnetpattern, throwerright, captainid(83),
                # personalityid, prev_el_champ, leftfreekicktakerid(86), cksupport2, leaguetitles, genericbanner,
                # crowdregion, uefa_uecl_wins, overallrating, ballid, profitability, utcoffset,
                # penaltytakerid(96), pitchlinecolor, cksupport5, freekicktakerid(99), crowdskintonecode,
                # internationalprestige, cksupport3, haslargeflag, trainingstadium, form, genericint1,
                # cksupport4, trait1vstrong, matchdayattackrating

                # Build the template with placeholders for dynamic values
                # Using sensible defaults for a new team
                captain = str(self.captain_id)
                team_values = [
                    str(self.team_id),  # 0: assetid (use team_id)
                    "26",               # 1: teamcolor1g
                    "218",              # 2: teamcolor1r
                    "1000000",          # 3: clubworth
                    "255",              # 4: teamcolor2b
                    "1",                # 5: goalnetstanchioncolor2g
                    "255",              # 6: teamcolor2r
                    "2000",             # 7: foundationyear
                    "1",                # 8: goalnetstanchioncolor2r
                    "228",              # 9: teamcolor3r
                    "1",                # 10: goalnetstanchioncolor1b
                    "53",               # 11: teamcolor1b
                    "3",                # 12: opponentweakthreshold
                    "0",                # 13: latitude
                    "206",              # 14: teamcolor3g
                    "3",                # 15: opponentstrongthreshold
                    "1",                # 16: goalnetstanchioncolor2b
                    "1",                # 17: goalnetstanchioncolor1r
                    "255",              # 18: teamcolor2g
                    "1",                # 19: goalnetstanchioncolor1g
                    self.team_name,     # 20: teamname
                    "60",               # 21: teamcolor3b
                    "0",                # 22: presassetone
                    "-1",               # 23: powid
                    "0",                # 24: hassubstitutionboard
                    captain,            # 25: rightfreekicktakerid
                    "0",                # 26: flamethrowercannon
                    "5",                # 27: domesticprestige
                    "-1",               # 28: genericint2
                    "0",                # 29: cksupport7
                    "50",               # 30: defensivedepth
                    "0",                # 31: hasvikingclap
                    "0",                # 32: jerseytype
                    "0",                # 33: pitchcolor
                    "0",                # 34: cksupport9
                    "0",                # 35: pitchwear
                    "5",                # 36: popularity
                    "0",                # 37: hastifo
                    "0",                # 38: presassettwo
                    "0",                # 39: teamstadiumcapacity
                    "0",                # 40: stadiumgoalnetstyle
                    "0",                # 41: iscompetitionscarfenabled
                    "0",                # 42: cityid
                    "0",                # 43: rivalteam
                    "1",                # 44: playsurfacetype
                    "0",                # 45: isbannerenabled
                    "75",               # 46: midfieldrating
                    "0",                # 47: cksupport8
                    "0",                # 48: stadiummowpattern_code
                    "0",                # 49: cksupport6
                    "75",               # 50: matchdayoverallrating
                    "75",               # 51: matchdaymidfieldrating
                    "75",               # 52: attackrating
                    "0",                # 53: longitude
                    "50",               # 54: buildupplay
                    "75",               # 55: matchdaydefenserating
                    "0",                # 56: hasstandingcrowd
                    "-1",               # 57: favoriteteamsheetid
                    "75",               # 58: defenserating
                    "0",                # 59: iscompetitionpoleflagenabled
                    "0",                # 60: skinnyflags
                    "0",                # 61: uefa_consecutive_wins
                    captain,            # 62: longkicktakerid
                    "0",                # 63: trait1vweak
                    "0",                # 64: iscompetitioncrowdcardsenabled
                    captain,            # 65: rightcornerkicktakerid
                    "0",                # 66: throwerleft
                    "0",                # 67: gender
                    "0",                # 68: cksupport1
                    "0",                # 69: cornerflagpolecolor
                    "0",                # 70: uefa_cl_wins
                    "0",                # 71: hassuncanthem
                    "0",                # 72: domesticcups
                    "0",                # 73: ethnicity
                    captain,            # 74: leftcornerkicktakerid
                    "5",                # 75: youthdevelopment
                    str(self.team_id),  # 76: teamid
                    "0",                # 77: uefa_el_wins
                    "0",                # 78: trait1vequal
                    "0",                # 79: numtransfersin
                    "0",                # 80: stanchionflamethrower
                    "0",                # 81: stadiumgoalnetpattern
                    "0",                # 82: throwerright
                    captain,            # 83: captainid
                    "0",                # 84: personalityid
                    "0",                # 85: prev_el_champ
                    captain,            # 86: leftfreekicktakerid
                    "0",                # 87: cksupport2
                    "0",                # 88: leaguetitles
                    "0",                # 89: genericbanner
                    "0",                # 90: crowdregion
                    "0",                # 91: uefa_uecl_wins
                    "75",               # 92: overallrating
                    "0",                # 93: ballid
                    "50",               # 94: profitability
                    "0",                # 95: utcoffset
                    captain,            # 96: penaltytakerid
                    "0",                # 97: pitchlinecolor
                    "0",                # 98: cksupport5
                    captain,            # 99: freekicktakerid
                    "0",                # 100: crowdskintonecode
                    "5",                # 101: internationalprestige
                    "0",                # 102: cksupport3
                    "0",                # 103: haslargeflag
                    "0",                # 104: trainingstadium
                    "50",               # 105: form
                    "-1",               # 106: genericint1
                    "0",                # 107: cksupport4
                    "0",                # 108: trait1vstrong
                    "75",               # 109: matchdayattackrating
                ]

                teams_template = "\t".join(team_values)

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + teams_template)

                print(f"✓ Added team to teams file: {file_path}")
                return True
            else:
                print(f"✗ Teams file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to teams file: {str(e)}")
            return False

    def append_to_teamsheets_file(self, file_path):
        """Append teamsheet with properly positioned players according to the header"""
        try:
            if os.path.exists(file_path):
                # Get our consistent player IDs - these are already in the correct order
                player_ids_raw = self.player_ids if self.player_ids else self.get_starting_player_ids()

                # Create a dictionary with playerid0, playerid1, etc. as keys
                player_id_dict = {}
                for i in range(len(player_ids_raw)):
                    player_id_dict[f"playerid{i}"] = str(player_ids_raw[i])

                # Check if we have a limited squad from teamplayerlinks method
                if hasattr(self, 'limited_squad') and self.is_national_team:
                    print("Using previously limited squad for teamsheet")
                    all_players = self.limited_squad

                    # Map the player IDs from the limited squad
                    for i, player in enumerate(all_players):
                        if i >= 11:  # Only update bench players (11+)
                            player_id_dict[f"playerid{i}"] = str(player['playerid'])
                else:
                    # Otherwise, build player list here
                    additional_players = []

                    # First, get players not already in the starting eleven
                    starting_player_ids = set(p['playerid'] for p in self.starting_eleven if p)

                    # For goalkeepers, handle differently based on team type
                    backup_gks = [p for p in self.goalkeepers if p['playerid'] not in starting_player_ids]
                    backup_gks.sort(key=lambda x: x.get('ovr', 0), reverse=True)

                    if self.is_national_team:
                        # For national teams: only 1 backup GK
                        if backup_gks:
                            additional_players.append(backup_gks[0])
                    else:
                        # For club teams: add ALL backup GKs
                        additional_players.extend(backup_gks)

                    # Add all field players not in starting eleven
                    field_players = [p for p in self.players if p['playerid'] not in starting_player_ids]
                    field_players.sort(key=lambda x: (x.get('pos_order', 999), -x.get('ovr', 0)))
                    additional_players.extend(field_players)

                    # For national teams, limit to 26 players total
                    if self.is_national_team:
                        max_additional = 26 - 11
                        additional_players = additional_players[:max_additional]

                    print(f"Additional players to assign: {len(additional_players)}")

                    # Assign all additional players to positions 11+ (up to position 51)
                    max_additional_positions = 52 - 11  # positions 11 through 51
                    for i, player in enumerate(additional_players):
                        if i < max_additional_positions:
                            player_id_dict[f"playerid{i + 11}"] = str(player['playerid'])
                            print(
                                f"Assigned player {player.get('given', '')} {player.get('sur', '')} to playerid{i + 11}")
                        else:
                            print(
                                f"Warning: More than {max_additional_positions} additional players, some will not be assigned positions")

                # Fill any missing positions with -1 (important for teamsheet structure)
                for i in range(52):
                    if f"playerid{i}" not in player_id_dict:
                        player_id_dict[f"playerid{i}"] = "-1"

                # Debug - print the first 11 players to verify
                print("\nTeamsheet player assignments:")
                for i in range(11):
                    player = next(
                        (p for p in self.starting_eleven if str(p['playerid']) == player_id_dict[f"playerid{i}"]), None)
                    if player:
                        print(
                            f"playerid{i}: {player_id_dict[f'playerid{i}']} ({player.get('given', '')} {player.get('sur', '')} - {player.get('pos1', '')})")
                    else:
                        print(f"playerid{i}: {player_id_dict[f'playerid{i}']} (Unknown)")

                # Define the exact teamsheet structure from the header
                teamsheet_structure = [
                    "playerid35", "playerid0", "playerid9", "customsub0in", "playerid36",
                    "rightfreekicktakerid", "playerid44", "playerid27", "playerid1", "playerid38",
                    "playerid31", "playerid7", "playerid20", "playerid39", "playerid42",
                    "playerid48", "playerid13", "playerid6", "customsub0out", "playerid37",
                    "playerid5", "playerid45", "playerid8", "playerid14", "playerid46",
                    "longkicktakerid", "playerid12", "playerid2", "rightcornerkicktakerid", "playerid30",
                    "customsub1in", "playerid15", "playerid41", "playerid47", "playerid23",
                    "playerid16", "customsub1out", "leftcornerkicktakerid", "playerid18", "playerid4",
                    "playerid40", "playerid49", "customsub2out", "teamid", "playerid22",
                    "playerid24", "playerid11", "customsub2in", "playerid3", "captainid",
                    "playerid51", "leftfreekicktakerid", "playerid25", "playerid33", "playerid19",
                    "playerid17", "playerid26", "playerid50", "playerid34", "penaltytakerid",
                    "playerid32", "freekicktakerid", "playerid28", "playerid21", "playerid10",
                    "playerid43", "playerid29"
                ]

                # Calculate total available players (starters + reserves)
                total_available = len(self.starting_eleven) + len(additional_players)
                print(f"Total available players: {total_available}")

                # Create the values list with special handling for non-player positions
                teamsheet_values = []
                for key in teamsheet_structure:
                    if key == "teamid":
                        teamsheet_values.append(str(self.team_id))
                    elif key == "captainid":
                        teamsheet_values.append(str(self.captain_id))
                    elif key == "rightfreekicktakerid" or key == "freekicktakerid":
                        # Try to use LW or another appropriate player
                        if "playerid10" in player_id_dict and player_id_dict["playerid10"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid10"])  # Use LW as right free kick taker
                        elif "playerid9" in player_id_dict and player_id_dict["playerid9"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid9"])  # Use ST as right free kick taker
                        else:
                            teamsheet_values.append(str(self.captain_id))  # Fallback to captain
                    elif key == "leftfreekicktakerid":
                        # Try to use RW or another appropriate player
                        if "playerid8" in player_id_dict and player_id_dict["playerid8"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid8"])  # Use RW as left free kick taker
                        elif "playerid9" in player_id_dict and player_id_dict["playerid9"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid9"])  # Use ST as fallback
                        else:
                            teamsheet_values.append(str(self.captain_id))  # Fallback to captain
                    elif key == "rightcornerkicktakerid":
                        # Try to use LW or another appropriate player
                        if "playerid10" in player_id_dict and player_id_dict["playerid10"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid10"])  # Use LW for right corner
                        elif "playerid9" in player_id_dict and player_id_dict["playerid9"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid9"])  # Use ST as fallback
                        else:
                            teamsheet_values.append(str(self.captain_id))  # Fallback to captain
                    elif key == "leftcornerkicktakerid":
                        # Try to use RW or another appropriate player
                        if "playerid8" in player_id_dict and player_id_dict["playerid8"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid8"])  # Use RW for left corner
                        elif "playerid9" in player_id_dict and player_id_dict["playerid9"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid9"])  # Use ST as fallback
                        else:
                            teamsheet_values.append(str(self.captain_id))  # Fallback to captain
                    elif key == "penaltytakerid":
                        # Try to use ST or another appropriate player
                        if "playerid9" in player_id_dict and player_id_dict["playerid9"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid9"])  # Use ST for penalties
                        else:
                            teamsheet_values.append(str(self.captain_id))  # Fallback to captain
                    elif key == "longkicktakerid":
                        # Try to use GK
                        if "playerid0" in player_id_dict and player_id_dict["playerid0"] != "-1":
                            teamsheet_values.append(player_id_dict["playerid0"])  # Use GK for goal kicks
                        else:
                            teamsheet_values.append("-1")  # No GK available
                    elif key.startswith("customsub"):
                        teamsheet_values.append("-1")  # Default for substitutions
                    elif key.startswith("playerid"):
                        teamsheet_values.append(player_id_dict.get(key, "-1"))
                    else:
                        teamsheet_values.append("-1")  # Default for any other positions

                # Create the final teamsheet line
                teamsheet_template = "\t".join(teamsheet_values)

                # Read the existing content (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Ensure there's a newline at the end
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new teamsheet and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + teamsheet_template)

                print(f"✓ Added teamsheet to file: {file_path} with all {total_available} available players")
                return True
            else:
                print(f"✗ Teamsheets file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to teamsheets file: {str(e)}")
            traceback.print_exc()  # Print full trace for debugging
            return False

    def append_to_mentalities_file(self, file_path, selected_formation=None):
        """Append mentalities using exact header mapping"""
        try:
            if os.path.exists(file_path):
                # Parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "mentalities")

                # Get the next mentality ID
                mentalityid_idx = header_dict.get('mentalityid')
                if mentalityid_idx is not None:
                    next_mentality_id = self.get_highest_id_from_file(file_path, mentalityid_idx, 3) + 1
                    print(f"Found mentalityid at column {mentalityid_idx}, next ID: {next_mentality_id}")
                else:
                    next_mentality_id = 4
                    print(f"Could not find mentalityid column, using default: {next_mentality_id}")

                # Read the existing content (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Get our consistent player IDs - SAME as used in teamsheet
                player_ids_raw = self.player_ids if self.player_ids else self.get_starting_player_ids()

                # Create a dictionary with playerid0, playerid1, etc. as keys
                player_id_dict = {}
                for i in range(len(player_ids_raw)):
                    player_id_dict[f"playerid{i}"] = str(player_ids_raw[i])

                # Define the mentalities structure from the header
                mentalities_structure = [
                    "offset6x", "offset5y", "offset10x", "offset2x", "offset2y",
                    "offset6y", "offset7x", "offset3x", "offset8x", "offset10y",
                    "offset3y", "offset4x", "offset7y", "offset0x", "offset8y",
                    "offset9x", "offset5x", "offset0y", "offset1x", "offset4y",
                    "offset9y", "offset1y", "pos0role", "pos6role", "pos8role",
                    "pos4role", "pos7role", "pos2role", "pos1role", "pos10role",
                    "pos3role", "pos9role", "pos5role", "tactic_name", "playerid0",
                    "playerid9", "position10", "defensivedepth", "playerid1",
                    "position6", "playerid7", "position8", "playerid6",
                    "buildupplay", "playerid5", "sourceformationid", "playerid8",
                    "playerid2", "position5", "formationaudioid", "playerid4",
                    "teamid", "position2", "playerid3", "position4", "position3",
                    "formationfullnameid", "mentalityid", "playerid10", "position0",
                    "position9", "position7", "position1"
                ]

                # Sample values based on selected formation or default to 4-3-3
                if selected_formation:
                    # Create a copy of the formation data to avoid modifying the original
                    formation_data = selected_formation.copy()
                    # Log the formation being used
                    print(f"Using formation {formation_data.get('name', '4-3-3')} for mentalities")

                    # Use formation-specific values when available
                    sample_values = {
                        "offset6x": formation_data.get("offset6x", "0.65"),
                        "offset5y": formation_data.get("offset5y", "0.3375"),
                        "offset10x": formation_data.get("offset10x", "0.075"),
                        "offset2x": formation_data.get("offset2x", "0.6731"),
                        "offset2y": formation_data.get("offset2y", "0.1537"),
                        "offset6y": formation_data.get("offset6y", "0.5125"),
                        "offset7x": formation_data.get("offset7x", "0.35"),
                        "offset3x": formation_data.get("offset3x", "0.325"),
                        "offset8x": formation_data.get("offset8x", "0.925"),
                        "offset10y": formation_data.get("offset10y", "0.825"),
                        "offset3y": formation_data.get("offset3y", "0.15"),
                        "offset4x": formation_data.get("offset4x", "0.075"),
                        "offset7y": formation_data.get("offset7y", "0.5125"),
                        "offset0x": formation_data.get("offset0x", "0.497"),
                        "offset8y": formation_data.get("offset8y", "0.825"),
                        "offset9x": formation_data.get("offset9x", "0.4995"),
                        "offset5x": formation_data.get("offset5x", "0.5"),
                        "offset0y": formation_data.get("offset0y", "0.0175"),
                        "offset1x": formation_data.get("offset1x", "0.9"),
                        "offset4y": formation_data.get("offset4y", "0.2"),
                        "offset9y": formation_data.get("offset9y", "0.875"),
                        "offset1y": formation_data.get("offset1y", "0.175"),
                        "pos0role": formation_data.get("pos0role", "4161"),
                        "pos6role": formation_data.get("pos6role", "21314"),
                        "pos8role": formation_data.get("pos8role", "33794"),
                        "pos4role": formation_data.get("pos4role", "8386"),
                        "pos7role": formation_data.get("pos7role", "21314"),
                        "pos2role": formation_data.get("pos2role", "12737"),
                        "pos1role": formation_data.get("pos1role", "8386"),
                        "pos10role": formation_data.get("pos10role", "33794"),
                        "pos3role": formation_data.get("pos3role", "12737"),
                        "pos9role": formation_data.get("pos9role", "12737"),
                        "pos5role": formation_data.get("pos5role", "17089"),
                        "tactic_name": formation_data.get("tactic_name", ""),
                        "position10": formation_data.get("position10", "27"),
                        "defensivedepth": formation_data.get("defensivedepth", "50"),
                        "position6": formation_data.get("position6", "13"),
                        "position8": formation_data.get("position8", "23"),
                        "buildupplay": formation_data.get("buildupplay", "2"),
                        "sourceformationid": "0",  # Don't use the formation's original ID
                        "position5": formation_data.get("position5", "10"),
                        "formationaudioid": formation_data.get("audio_id", "6"),
                        "position2": formation_data.get("position2", "4"),
                        "position4": formation_data.get("position4", "7"),
                        "position3": formation_data.get("position3", "6"),
                        "formationfullnameid": formation_data.get("fullname_id", "7"),
                        "position0": formation_data.get("position0", "0"),
                        "position9": formation_data.get("position9", "25"),
                        "position7": formation_data.get("position7", "15"),
                        "position1": formation_data.get("position1", "3")
                    }
                else:
                    # Default 4-3-3 formation values
                    sample_values = {
                        "offset6x": "0.65", "offset5y": "0.3375", "offset10x": "0.075", "offset2x": "0.6731",
                        "offset2y": "0.1537", "offset6y": "0.5125", "offset7x": "0.35", "offset3x": "0.325",
                        "offset8x": "0.925", "offset10y": "0.825", "offset3y": "0.15", "offset4x": "0.075",
                        "offset7y": "0.5125", "offset0x": "0.497", "offset8y": "0.825", "offset9x": "0.4995",
                        "offset5x": "0.5", "offset0y": "0.0175", "offset1x": "0.9", "offset4y": "0.2",
                        "offset9y": "0.875", "offset1y": "0.175",
                        "pos0role": "4161", "pos6role": "21314", "pos8role": "33794", "pos4role": "8386",
                        "pos7role": "21314", "pos2role": "12737", "pos1role": "8386", "pos10role": "33794",
                        "pos3role": "12737", "pos9role": "12737", "pos5role": "17089",
                        "tactic_name": "",
                        "position10": "27", "defensivedepth": "50", "position6": "13", "position8": "23",
                        "buildupplay": "2", "sourceformationid": "0", "position5": "10", "formationaudioid": "6",
                        "position2": "4", "position4": "7", "position3": "6", "formationfullnameid": "7",
                        "position0": "0", "position9": "25", "position7": "15", "position1": "3"
                    }
                    print("Using default 4-3-3 formation data for mentalities")

                # First mentality (active)
                mentality_values = []
                for key in mentalities_structure:
                    if key == "teamid":
                        mentality_values.append(str(self.team_id))
                    elif key == "mentalityid":
                        mentality_values.append(str(next_mentality_id))
                    elif key.startswith("playerid") and key in player_id_dict:
                        mentality_values.append(str(player_id_dict[key]))
                    elif key in sample_values:
                        mentality_values.append(str(sample_values[key]))  # Ensure string conversion
                    else:
                        mentality_values.append("-1")  # Default fallback

                # Create two additional inactive mentality entries with the same structure
                inactive_mentalityid1 = str(next_mentality_id + 1)
                inactive_mentalityid2 = str(next_mentality_id + 2)

                # Build the inactive mentality templates - mostly -1 values
                inactive_mentality1 = ["0"] * 33 + [""] + ["-1", "-1", "-1", "1", "-1", "-1", "-1", "-1", "-1", "0",
                                                           "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1",
                                                           "-1", "-1", "-1", inactive_mentalityid1, "-1", "-1", "-1",
                                                           "-1", "-1"]

                inactive_mentality2 = ["0"] * 33 + [""] + ["-1", "-1", "-1", "1", "-1", "-1", "-1", "-1", "-1", "0",
                                                           "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1", "-1",
                                                           "-1", "-1", "-1", inactive_mentalityid2, "-1", "-1", "-1",
                                                           "-1", "-1"]

                # Build the final mentalities template - active + 2 inactive
                mentalities_template = "\t".join(mentality_values) + "\n" + \
                                       "\t".join(inactive_mentality1) + "\n" + \
                                       "\t".join(inactive_mentality2)

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new mentalities to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + mentalities_template)

                print(f"✓ Added mentalities to file: {file_path}")
                return True
            else:
                print(f"✗ Mentalities file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to mentalities file: {str(e)}")
            traceback.print_exc()
            return False

    def append_to_leagueteamlinks_file(self, file_path):
        """Append league team link to the leagueteamlinks.txt file"""
        try:
            if os.path.exists(file_path):
                # Parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "leagueteamlinks")

                # Get the next artificial key from the correct column
                artificialkey_idx = header_dict.get('artificialkey')
                if artificialkey_idx is not None:
                    next_key = self.get_highest_id_from_file(file_path, artificialkey_idx, 0) + 1
                    print(f"Found artificialkey at column {artificialkey_idx}, next key: {next_key}")
                else:
                    next_key = 1
                    print(f"Could not find artificialkey column, using default: {next_key}")

                # Read the entire content to keep it (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Template structure from the user's example
                leagueteamlinks_template = f"""0\t1\t0\t1\t0\t0\t0\t0\t0\t0\t0\t0\t{self.league_id}\t{self.league_id}\t0\t0\t0\t0\t{next_key}\t0\t{self.team_id}\t0\t0\t0\t0\t0\t0\t0\t-1\t0\t0\t0\t0\t0"""

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new link to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + leagueteamlinks_template)

                print(f"✓ Added league team link to file: {file_path}")
                return True
            else:
                print(f"✗ Leagueteamlinks file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to leagueteamlinks file: {str(e)}")
            traceback.print_exc()
            return False

    def append_to_manager_file(self, file_path):
        """Append manager to the manager.txt file"""
        try:
            if os.path.exists(file_path):
                # Parse the header to understand the file structure
                header_dict = self.parse_file_header(file_path, "manager")

                # Get the next manager ID from the correct column
                managerid_idx = header_dict.get('managerid')
                if managerid_idx is not None:
                    next_manager_id = self.get_highest_id_from_file(file_path, managerid_idx, 254782) + 1
                    print(f"Found managerid at column {managerid_idx}, next ID: {next_manager_id}")
                else:
                    next_manager_id = 254783
                    print(f"Could not find managerid column, using default: {next_manager_id}")

                # Read the entire content to keep it (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # New header structure (53 columns):
                # starrating, firstname, commonname, surname, eyebrowcode, skintypecode, haircolorcode,
                # facialhairtypecode, managerid(8), accessorycode4, hairtypecode, facepsdlayer0, lipcolor,
                # skinsurfacepack, accessorycode3, accessorycolourcode1, headtypecode, height, seasonaloutfitid,
                # birthdate, isrewardable, skinmakeup, trait1vweak, weight, hashighqualityhead, eyedetail,
                # gender, headassetid, ethnicity, faceposerpreset, islicensed, teamid(31), trait1vequal,
                # eyecolorcode, personalityid, accessorycolourcode3, accessorycode1, headclasscode,
                # nationality, sideburnscode, accessorycolourcode4, headvariation, skintonecode, outfitid,
                # facepsdlayer1, skincomplexion, accessorycode2, hairstylecode, bodytypecode,
                # managerjointeamdate, trait1vstrong, accessorycolourcode2, facialhaircolorcode

                manager_values = [
                    "2",                    # 0: starrating (default 2 as requested)
                    "Manager",              # 1: firstname
                    "",                     # 2: commonname
                    "Manager",              # 3: surname
                    "0",                    # 4: eyebrowcode
                    "0",                    # 5: skintypecode
                    "24",                   # 6: haircolorcode
                    "0",                    # 7: facialhairtypecode
                    str(next_manager_id),   # 8: managerid
                    "0",                    # 9: accessorycode4
                    "0",                    # 10: hairtypecode
                    "0",                    # 11: facepsdlayer0
                    "0",                    # 12: lipcolor
                    "0",                    # 13: skinsurfacepack
                    "0",                    # 14: accessorycode3
                    "0",                    # 15: accessorycolourcode1
                    "0",                    # 16: headtypecode
                    "180",                  # 17: height
                    "0",                    # 18: seasonaloutfitid
                    "142606",               # 19: birthdate (placeholder date)
                    "0",                    # 20: isrewardable
                    "0",                    # 21: skinmakeup
                    "0",                    # 22: trait1vweak
                    "80",                   # 23: weight
                    "0",                    # 24: hashighqualityhead
                    "0",                    # 25: eyedetail
                    "0",                    # 26: gender
                    "0",                    # 27: headassetid
                    "0",                    # 28: ethnicity
                    "0",                    # 29: faceposerpreset
                    "0",                    # 30: islicensed
                    str(self.team_id),      # 31: teamid
                    "0",                    # 32: trait1vequal
                    "3",                    # 33: eyecolorcode
                    "0",                    # 34: personalityid
                    "0",                    # 35: accessorycolourcode3
                    "0",                    # 36: accessorycode1
                    "0",                    # 37: headclasscode
                    "1",                    # 38: nationality
                    "0",                    # 39: sideburnscode
                    "0",                    # 40: accessorycolourcode4
                    "0",                    # 41: headvariation
                    "3",                    # 42: skintonecode
                    "0",                    # 43: outfitid
                    "0",                    # 44: facepsdlayer1
                    "0",                    # 45: skincomplexion
                    "0",                    # 46: accessorycode2
                    "0",                    # 47: hairstylecode
                    "3",                    # 48: bodytypecode
                    "161224",               # 49: managerjointeamdate
                    "0",                    # 50: trait1vstrong
                    "0",                    # 51: accessorycolourcode2
                    "0",                    # 52: facialhaircolorcode
                ]

                manager_template = "\t".join(manager_values)

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new manager to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + manager_template)

                print(f"✓ Added manager to file: {file_path}")
                return True
            else:
                print(f"✗ Manager file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to manager file: {str(e)}")
            traceback.print_exc()
            return False

    def append_to_teamkits_file(self, file_path):
        """Append team kits to the teamkits.txt file"""
        try:
            if os.path.exists(file_path):
                # Read the entire content to keep it (auto-detect encoding)
                file_encoding = detect_file_encoding(file_path)
                with open(file_path, 'r', encoding=file_encoding) as file:
                    content = file.read()

                # Find all kit IDs at the start of lines
                kit_ids = re.findall(r'^(\d+)', content, re.MULTILINE)

                # Use the highest ID as our base for the next one
                next_kit_id = 17127  # Default
                if kit_ids:
                    try:
                        highest_kit_id = max([int(kid) for kid in kit_ids if kid.isdigit()])
                        next_kit_id = highest_kit_id + 1
                        print(f"Found {len(kit_ids)} kit IDs. Highest: {highest_kit_id}, Next: {next_kit_id}")
                    except (ValueError, IndexError):
                        print(f"Warning: Could not parse kit IDs, using default: {next_kit_id}")
                else:
                    print(f"No kit IDs found, using default: {next_kit_id}")

                # New header structure (72 columns):
                # teamkitid, chestbadge, shortsnumberplacementcode, shortsnumbercolorprimg, teamcolorsecb,
                # shortsrenderingdetailmaptype, jerseyfrontnumberplacementcode, jerseynumbercolorsecr,
                # jerseynumbercolorprimr, jerseynumbercolorprimg, shortsnumbercolorsecb, teamcolorprimg,
                # shortsnumbercolorterb, shortsnumbercolorprimr, teamcolortertb, jerseynumbercolorterg,
                # jerseynameoutlinecolorr, shortsnumbercolorprimb, jerseynamelayouttype, jerseynumbercolorterr,
                # jerseyrightsleevebadge, jerseynumbercolorprimb, jerseyshapestyle, jerseybacknameplacementcode,
                # teamcolorprimr, jerseynamecolorg, jerseyleftsleevebadge, jerseynameoutlinecolorb, teamcolorsecg,
                # shortsnumbercolorsecg, teamcolortertr, jerseynumbercolorsecg, renderingmaterialtype,
                # shortsnumbercolorterr, teamcolorsecr, jerseycollargeometrytype, shortsnumbercolorterg,
                # jerseynamecolorr, teamcolorprimb, jerseyrenderingdetailmaptype, jerseynameoutlinecolorg,
                # jerseynumbercolorsecb, jerseynamecolorb, jerseynumbercolorterb, teamcolortertg,
                # shortsnumbercolorsecr, jerseybacknamefontcase, teamkittypetechid(47), powid, isinheritbasedetailmap,
                # islocked, numberfonttype, shortstemplateindex, jerseynamefonttype, teamcolorprimpercent,
                # isgeneric, teamcolorsecpercent, year, jerseytemplateindex, captainarmband, teamtechid(60),
                # isembargoed, hasadvertisingkit, jerseynameoutlinewidth, dlc, teamcolortertpercent, armbandtype,
                # shortsnumberfonttype, shortstyle, jerseyfit, sockstemplateindex, jerseyrestriction

                # Home kit (teamkittypetechid = 0)
                home_kit = [
                    str(next_kit_id),   # 0: teamkitid
                    "0",                # 1: chestbadge
                    "1",                # 2: shortsnumberplacementcode
                    "12",               # 3: shortsnumbercolorprimg
                    "34",               # 4: teamcolorsecb
                    "0",                # 5: shortsrenderingdetailmaptype
                    "1",                # 6: jerseyfrontnumberplacementcode
                    "220",              # 7: jerseynumbercolorsecr
                    "45",               # 8: jerseynumbercolorprimr
                    "42",               # 9: jerseynumbercolorprimg
                    "12",               # 10: shortsnumbercolorsecb
                    "222",              # 11: teamcolorprimg
                    "12",               # 12: shortsnumbercolorterb
                    "12",               # 13: shortsnumbercolorprimr
                    "219",              # 14: teamcolortertb
                    "12",               # 15: jerseynumbercolorterg
                    "45",               # 16: jerseynameoutlinecolorr
                    "12",               # 17: shortsnumbercolorprimb
                    "0",                # 18: jerseynamelayouttype
                    "12",               # 19: jerseynumbercolorterr
                    "0",                # 20: jerseyrightsleevebadge
                    "38",               # 21: jerseynumbercolorprimb
                    "0",                # 22: jerseyshapestyle
                    "1",                # 23: jerseybacknameplacementcode
                    "224",              # 24: teamcolorprimr
                    "42",               # 25: jerseynamecolorg
                    "0",                # 26: jerseyleftsleevebadge
                    "38",               # 27: jerseynameoutlinecolorb
                    "35",               # 28: teamcolorsecg
                    "12",               # 29: shortsnumbercolorsecg
                    "222",              # 30: teamcolortertr
                    "220",              # 31: jerseynumbercolorsecg
                    "0",                # 32: renderingmaterialtype
                    "12",               # 33: shortsnumbercolorterr
                    "39",               # 34: teamcolorsecr
                    "0",                # 35: jerseycollargeometrytype
                    "12",               # 36: shortsnumbercolorterg
                    "45",               # 37: jerseynamecolorr
                    "219",              # 38: teamcolorprimb
                    "0",                # 39: jerseyrenderingdetailmaptype
                    "42",               # 40: jerseynameoutlinecolorg
                    "220",              # 41: jerseynumbercolorsecb
                    "38",               # 42: jerseynamecolorb
                    "12",               # 43: jerseynumbercolorterb
                    "222",              # 44: teamcolortertg
                    "12",               # 45: shortsnumbercolorsecr
                    "0",                # 46: jerseybacknamefontcase
                    "0",                # 47: teamkittypetechid (0=home)
                    "-1",               # 48: powid
                    "0",                # 49: isinheritbasedetailmap
                    "0",                # 50: islocked
                    "123",              # 51: numberfonttype
                    "101",              # 52: shortstemplateindex
                    "88",               # 53: jerseynamefonttype
                    "5",                # 54: teamcolorprimpercent
                    "0",                # 55: isgeneric
                    "78",               # 56: teamcolorsecpercent
                    "0",                # 57: year
                    "0",                # 58: jerseytemplateindex
                    "0",                # 59: captainarmband
                    str(self.team_id),  # 60: teamtechid
                    "0",                # 61: isembargoed
                    "0",                # 62: hasadvertisingkit
                    "0",                # 63: jerseynameoutlinewidth
                    "0",                # 64: dlc
                    "90",               # 65: teamcolortertpercent
                    "1",                # 66: armbandtype
                    "123",              # 67: shortsnumberfonttype
                    "0",                # 68: shortstyle
                    "0",                # 69: jerseyfit
                    "0",                # 70: sockstemplateindex
                    "0",                # 71: jerseyrestriction
                ]

                # Away kit (teamkittypetechid = 1)
                away_kit = [
                    str(next_kit_id + 1),  # 0: teamkitid
                    "0",                # 1: chestbadge
                    "1",                # 2: shortsnumberplacementcode
                    "220",              # 3: shortsnumbercolorprimg
                    "92",               # 4: teamcolorsecb
                    "0",                # 5: shortsrenderingdetailmaptype
                    "1",                # 6: jerseyfrontnumberplacementcode
                    "12",               # 7: jerseynumbercolorsecr
                    "220",              # 8: jerseynumbercolorprimr
                    "220",              # 9: jerseynumbercolorprimg
                    "220",              # 10: shortsnumbercolorsecb
                    "60",               # 11: teamcolorprimg
                    "220",              # 12: shortsnumbercolorterb
                    "220",              # 13: shortsnumbercolorprimr
                    "89",               # 14: teamcolortertb
                    "220",              # 15: jerseynumbercolorterg
                    "220",              # 16: jerseynameoutlinecolorr
                    "220",              # 17: shortsnumbercolorprimb
                    "0",                # 18: jerseynamelayouttype
                    "220",              # 19: jerseynumbercolorterr
                    "0",                # 20: jerseyrightsleevebadge
                    "220",              # 21: jerseynumbercolorprimb
                    "0",                # 22: jerseyshapestyle
                    "1",                # 23: jerseybacknameplacementcode
                    "179",              # 24: teamcolorprimr
                    "220",              # 25: jerseynamecolorg
                    "0",                # 26: jerseyleftsleevebadge
                    "220",              # 27: jerseynameoutlinecolorb
                    "40",               # 28: teamcolorsecg
                    "220",              # 29: shortsnumbercolorsecg
                    "51",               # 30: teamcolortertr
                    "12",               # 31: jerseynumbercolorsecg
                    "0",                # 32: renderingmaterialtype
                    "220",              # 33: shortsnumbercolorterr
                    "58",               # 34: teamcolorsecr
                    "0",                # 35: jerseycollargeometrytype
                    "220",              # 36: shortsnumbercolorterg
                    "220",              # 37: jerseynamecolorr
                    "127",              # 38: teamcolorprimb
                    "0",                # 39: jerseyrenderingdetailmaptype
                    "220",              # 40: jerseynameoutlinecolorg
                    "12",               # 41: jerseynumbercolorsecb
                    "220",              # 42: jerseynamecolorb
                    "220",              # 43: jerseynumbercolorterb
                    "37",               # 44: teamcolortertg
                    "220",              # 45: shortsnumbercolorsecr
                    "0",                # 46: jerseybacknamefontcase
                    "1",                # 47: teamkittypetechid (1=away)
                    "-1",               # 48: powid
                    "0",                # 49: isinheritbasedetailmap
                    "0",                # 50: islocked
                    "123",              # 51: numberfonttype
                    "101",              # 52: shortstemplateindex
                    "53",               # 53: jerseynamefonttype
                    "44",               # 54: teamcolorprimpercent
                    "0",                # 55: isgeneric
                    "78",               # 56: teamcolorsecpercent
                    "0",                # 57: year
                    "0",                # 58: jerseytemplateindex
                    "0",                # 59: captainarmband
                    str(self.team_id),  # 60: teamtechid
                    "0",                # 61: isembargoed
                    "0",                # 62: hasadvertisingkit
                    "0",                # 63: jerseynameoutlinewidth
                    "0",                # 64: dlc
                    "89",               # 65: teamcolortertpercent
                    "0",                # 66: armbandtype
                    "123",              # 67: shortsnumberfonttype
                    "0",                # 68: shortstyle
                    "0",                # 69: jerseyfit
                    "0",                # 70: sockstemplateindex
                    "0",                # 71: jerseyrestriction
                ]

                # Third kit (teamkittypetechid = 2)
                third_kit = [
                    str(next_kit_id + 2),  # 0: teamkitid
                    "0",                # 1: chestbadge
                    "1",                # 2: shortsnumberplacementcode
                    "229",              # 3: shortsnumbercolorprimg
                    "84",               # 4: teamcolorsecb
                    "0",                # 5: shortsrenderingdetailmaptype
                    "1",                # 6: jerseyfrontnumberplacementcode
                    "12",               # 7: jerseynumbercolorsecr
                    "220",              # 8: jerseynumbercolorprimr
                    "229",              # 9: jerseynumbercolorprimg
                    "22",               # 10: shortsnumbercolorsecb
                    "30",               # 11: teamcolorprimg
                    "22",               # 12: shortsnumbercolorterb
                    "220",              # 13: shortsnumbercolorprimr
                    "29",               # 14: teamcolortertb
                    "229",              # 15: jerseynumbercolorterg
                    "220",              # 16: jerseynameoutlinecolorr
                    "22",               # 17: shortsnumbercolorprimb
                    "0",                # 18: jerseynamelayouttype
                    "220",              # 19: jerseynumbercolorterr
                    "0",                # 20: jerseyrightsleevebadge
                    "22",               # 21: jerseynumbercolorprimb
                    "0",                # 22: jerseyshapestyle
                    "1",                # 23: jerseybacknameplacementcode
                    "32",               # 24: teamcolorprimr
                    "229",              # 25: jerseynamecolorg
                    "0",                # 26: jerseyleftsleevebadge
                    "220",              # 27: jerseynameoutlinecolorb
                    "83",               # 28: teamcolorsecg
                    "229",              # 29: shortsnumbercolorsecg
                    "29",               # 30: teamcolortertr
                    "12",               # 31: jerseynumbercolorsecg
                    "0",                # 32: renderingmaterialtype
                    "220",              # 33: shortsnumbercolorterr
                    "86",               # 34: teamcolorsecr
                    "7",                # 35: jerseycollargeometrytype
                    "229",              # 36: shortsnumbercolorterg
                    "220",              # 37: jerseynamecolorr
                    "30",               # 38: teamcolorprimb
                    "0",                # 39: jerseyrenderingdetailmaptype
                    "220",              # 40: jerseynameoutlinecolorg
                    "12",               # 41: jerseynumbercolorsecb
                    "22",               # 42: jerseynamecolorb
                    "22",               # 43: jerseynumbercolorterb
                    "29",               # 44: teamcolortertg
                    "220",              # 45: shortsnumbercolorsecr
                    "0",                # 46: jerseybacknamefontcase
                    "2",                # 47: teamkittypetechid (2=third)
                    "-1",               # 48: powid
                    "0",                # 49: isinheritbasedetailmap
                    "0",                # 50: islocked
                    "123",              # 51: numberfonttype
                    "101",              # 52: shortstemplateindex
                    "81",               # 53: jerseynamefonttype
                    "9",                # 54: teamcolorprimpercent
                    "0",                # 55: isgeneric
                    "78",               # 56: teamcolorsecpercent
                    "0",                # 57: year
                    "0",                # 58: jerseytemplateindex
                    "0",                # 59: captainarmband
                    str(self.team_id),  # 60: teamtechid
                    "0",                # 61: isembargoed
                    "0",                # 62: hasadvertisingkit
                    "0",                # 63: jerseynameoutlinewidth
                    "0",                # 64: dlc
                    "97",               # 65: teamcolortertpercent
                    "0",                # 66: armbandtype
                    "123",              # 67: shortsnumberfonttype
                    "0",                # 68: shortstyle
                    "0",                # 69: jerseyfit
                    "0",                # 70: sockstemplateindex
                    "0",                # 71: jerseyrestriction
                ]

                # Join each kit into tab-separated lines
                teamkits_template = "\t".join(home_kit) + "\n" + "\t".join(away_kit) + "\n" + "\t".join(third_kit)

                # Ensure there's a newline at the end of the original content
                if content and not content.endswith('\n'):
                    content += '\n'

                # Append the new kits to the content and write back
                with open(file_path, 'w', encoding=file_encoding) as file:
                    file.write(content + teamkits_template)

                print(f"✓ Added team kits to file: {file_path}")
                return True
            else:
                print(f"✗ Teamkits file not found: {file_path}")
                return False
        except Exception as e:
            print(f"✗ Error appending to teamkits file: {str(e)}")
            return False

    def process_files(self, input_dir, selected_formation=None):
        """
        Process all the required files for team creation

        Args:
            input_dir (str): Directory containing all input files
            selected_formation (dict, optional): Formation data to use
        """
        print("\n" + "=" * 50)
        print(f"TEAM CREATION: {self.team_name} (ID: {self.team_id})")
        print(f"League ID: {self.league_id}")
        print(f"Captain ID: {self.captain_id}")
        if self.is_national_team:
            print(f"Nation ID: {self.nation_id}")
        if self.stadium_id is not None:
            print(f"Stadium ID: {self.stadium_id}")
        if selected_formation:
            print(f"Formation: {selected_formation['name']}")
        print(f"Directory: {input_dir}")
        print("=" * 50 + "\n")

        # List of files to process and their corresponding methods
        file_processes = [
            ("teams.txt", self.append_to_teams_file),
            ("default_mentalities.txt", lambda path: self.append_to_mentalities_file(path, selected_formation)),
            ("default_teamsheets.txt", self.append_to_teamsheets_file),
            ("formations.txt", lambda path: self.append_to_formations_file(path, selected_formation)),
            ("leagueteamlinks.txt", self.append_to_leagueteamlinks_file),
            ("manager.txt", self.append_to_manager_file),
            ("teamkits.txt", self.append_to_teamkits_file),
            ("teamplayerlinks.txt", self.append_to_teamplayerlinks_file)
        ]

        # Add teamnationlinks.txt for national teams
        if self.is_national_team:
            file_processes.append(("teamnationlinks.txt", self.append_to_team_nationlinks_file))

        # Add teamstadiumlinks.txt if a stadium ID is specified
        if self.stadium_id is not None:
            file_processes.append(("teamstadiumlinks.txt", self.append_to_teamstadiumlinks_file))

        # Process each file
        success_count = 0
        error_count = 0

        for filename, method in file_processes:
            file_path = os.path.join(input_dir, filename)
            success = method(file_path)

            if success:
                success_count += 1
            else:
                error_count += 1

        # Print summary
        print("\n" + "=" * 50)
        print(f"PROCESSING COMPLETE: {success_count} files modified successfully, {error_count} errors")
        print("=" * 50 + "\n")

        return success_count > 0


def process_multiple_teams(team_files, starting_team_id, league_id, input_dir, is_national_teams=False,
                           players_txt_path=None, nation_id_map=None):
    """
    Process multiple teams one after another

    Args:
        team_files (list): List of paths to player CSV/TXT files (or nation names for national teams)
        starting_team_id (int): ID to assign to the first team
        league_id (int): League ID to use for all teams (78 for national teams)
        input_dir (str): Directory containing all game files
        is_national_teams (bool): Whether these are national teams
        players_txt_path (str): Path to players.txt file for national teams
        nation_id_map (dict): Mapping of nation names to nation IDs

    Returns:
        int: Number of teams successfully processed
    """
    print(f"\nProcessing {len(team_files)} teams starting with ID: {starting_team_id}")

    if is_national_teams:
        print("Processing as NATIONAL TEAMS")
        print(f"Using players.txt file: {players_txt_path}")
        league_id = 78  # Always 78 for national teams

    print(f"All teams will be assigned to league ID: {league_id}")

    success_count = 0
    current_team_id = starting_team_id

    for i, team_file_or_name in enumerate(team_files):
        try:
            if is_national_teams:
                # For national teams, team_file_or_name is the nation name
                team_name = team_file_or_name
                nation_id = nation_id_map.get(team_name)

                if not nation_id:
                    print(f"✗ Could not find nation ID for {team_name}. Skipping.")
                    continue

                print(
                    f"\nProcessing national team {i + 1}/{len(team_files)}: {team_name} (ID: {current_team_id}, Nation ID: {nation_id})")

                # Create a team appender for this national team
                appender = TeamAppender(team_name, current_team_id, league_id, nation_id, is_national_team=True)

                # Load player data from players.txt
                if not appender.load_player_data(players_txt_path):
                    print(f"✗ Failed to load player data for {team_name}. Skipping.")
                    continue
            else:
                # Regular club team processing
                team_file = team_file_or_name

                # Extract team name from the filename
                team_name = os.path.basename(team_file)
                if team_name.lower().endswith('.csv') or team_name.lower().endswith('.txt'):
                    team_name = team_name[:-4]  # Remove extension

                print(f"\nProcessing team {i + 1}/{len(team_files)}: {team_name} (ID: {current_team_id})")

                # Create a team appender for this team
                appender = TeamAppender(team_name, current_team_id, league_id)

                # Load player data
                if not appender.load_player_data(team_file):
                    print(f"✗ Failed to load player data for {team_name}. Skipping.")
                    continue

            # Process all files
            if appender.process_files(input_dir):
                success_count += 1
                print(f"✓ Team {team_name} processed successfully.")
            else:
                print(f"✗ Some errors occurred while processing team {team_name}.")

            # Increment team ID for the next team
            current_team_id += 1
        except Exception as e:
            print(f"✗ Error processing team {team_file_or_name}: {str(e)}")
            traceback.print_exc()
            continue

    return success_count


def load_blacklisted_players():
    """Load the blacklisted player IDs that should be excluded from national teams"""
    # Hardcoded list of blacklisted player IDs
    blacklist = [
        27, 51, 240, 246, 250, 330, 524, 570, 1025, 1041, 1088, 1114, 1116, 1179, 1183, 1201, 1397, 1551, 1605, 1615,
        1620, 1625, 1668, 1845, 3622, 4231, 4833, 5003, 5419, 5454, 5467, 5471, 5479, 5589, 5661, 5673, 5679, 5740,
        6235, 6975, 7289, 7512, 7743, 7763, 8385, 8473, 9676, 10264, 10535, 13128, 13743, 15723, 16254, 16619, 20289,
        23174, 25924, 26709, 28130, 28765, 30110, 31432, 34079, 37576, 39386, 40898, 44897, 45197, 45661, 45674, 48940,
        49369, 50752, 51257, 51412, 51539, 54050, 71557, 71587, 71608, 120274, 121939, 121944, 135455, 138449, 140601,
        142754, 150418, 155897, 156353, 156616, 161840, 164994, 166124, 166149, 166676, 166691, 166906, 167134, 167135,
        167198, 167425, 167680, 168880, 168886, 170890, 171877, 173210, 183277, 184943, 190042, 190044, 190045, 190046,
        190048, 191694, 191695, 191972, 192181, 214098, 214100, 214101, 214267, 214649, 222000, 226293, 226306, 226369,
        226373, 226764, 227002, 227006, 227261, 227263, 227271, 227315, 227324, 230025, 233700, 237067, 238380, 238382,
        238384, 238388, 238424, 238427, 238428, 238430, 238435, 238439, 238443, 239261, 242510, 242519, 242625, 243027,
        243029, 243030, 247515, 247553, 247699, 247703, 248146, 250890, 251483, 254642, 261593, 262112, 262271, 262285,
        266473, 266690, 266691, 266694, 266695, 266801, 268513, 269603, 273812, 274750, 274966, 274967, 275049, 275092,
        275243, 275276, 1256, 3647, 5984, 176676, 176580
    ]

    # Convert to a set for faster lookups
    blacklist_set = set(blacklist)
    print(f"Loaded {len(blacklist_set)} blacklisted player IDs")
    return blacklist_set


def load_nation_id_mapping():
    """Load the mapping of nation names to nation IDs directly from FIFA's data"""
    print("Loading nation ID mapping")

    # Direct mapping of nation names to IDs based on provided FIFA data
    nation_mapping = {
        "Albania": 1, "Andorra": 2, "Armenia": 3, "Austria": 4, "Azerbaijan": 5,
        "Belarus": 6, "Belgium": 7, "Bosnia and Herzegovina": 8, "Bulgaria": 9, "Croatia": 10,
        "Cyprus": 11, "Czech Republic": 12, "Denmark": 13, "England": 14, "Montenegro": 15,
        "Faroe Islands": 16, "Finland": 17, "France": 18, "North Macedonia": 19, "Georgia": 20,
        "Germany": 21, "Greece": 22, "Hungary": 23, "Iceland": 24, "Republic of Ireland": 25,
        "Israel": 26, "Italy": 27, "Latvia": 28, "Liechtenstein": 29, "Lithuania": 30,
        "Luxembourg": 31, "Malta": 32, "Moldova": 33, "Holland": 34, "Northern Ireland": 35,
        "Norway": 36, "Poland": 37, "Portugal": 38, "Romania": 39, "Russia": 40,
        "San Marino": 41, "Scotland": 42, "Slovakia": 43, "Slovenia": 44, "Spain": 45,
        "Sweden": 46, "Switzerland": 47, "Turkey": 48, "Ukraine": 49, "Wales": 50,
        "Serbia": 51, "Argentina": 52, "Bolivia": 53, "Brazil": 54, "Chile": 55,
        "Colombia": 56, "Ecuador": 57, "Paraguay": 58, "Peru": 59, "Uruguay": 60,
        "Venezuela": 61, "Anguilla": 62, "Antigua and Barbuda": 63, "Aruba": 64, "Bahamas": 65,
        "Barbados": 66, "Belize": 67, "Bermuda": 68, "British Virgin Islands": 69, "Canada": 70,
        "Cayman Islands": 71, "Costa Rica": 72, "Cuba": 73, "Dominica": 74, "International": 75,
        "El Salvador": 76, "Grenada": 77, "Guatemala": 78, "Guyana": 79, "Haiti": 80,
        "Honduras": 81, "Jamaica": 82, "Mexico": 83, "Montserrat": 84, "Curaçao": 85,
        "Nicaragua": 86, "Panama": 87, "Puerto Rico": 88, "St. Kitts and Nevis": 89, "St. Lucia": 90,
        "St. Vincent and the Grenadines": 91, "Suriname": 92, "Trinidad and Tobago": 93,
        "Turks and Caicos Islands": 94, "United States": 95, "US Virgin Islands": 96, "Algeria": 97,
        "Angola": 98, "Benin": 99, "Botswana": 100, "Burkina Faso": 101, "Burundi": 102,
        "Cameroon": 103, "Cape Verde Islands": 104, "Central African Republic": 105, "Chad": 106,
        "Congo": 107, "Côte d'Ivoire": 108, "Djibouti": 109, "Congo DR": 110, "Egypt": 111,
        "Equatorial Guinea": 112, "Eritrea": 113, "Ethiopia": 114, "Gabon": 115, "Gambia": 116,
        "Ghana": 117, "Guinea": 118, "Guinea-Bissau": 119, "Kenya": 120, "Lesotho": 121,
        "Liberia": 122, "Libya": 123, "Madagascar": 124, "Malawi": 125, "Mali": 126,
        "Mauritania": 127, "Mauritius": 128, "Morocco": 129, "Mozambique": 130, "Namibia": 131,
        "Niger": 132, "Nigeria": 133, "Rwanda": 134, "São Tomé e Príncipe": 135, "Senegal": 136,
        "Seychelles": 137, "Sierra Leone": 138, "Somalia": 139, "South Africa": 140, "Sudan": 141,
        "Eswatini": 142, "Tanzania": 143, "Togo": 144, "Tunisia": 145, "Uganda": 146,
        "Zambia": 147, "Zimbabwe": 148, "Afghanistan": 149, "Bahrain": 150, "Bangladesh": 151,
        "Bhutan": 152, "Brunei Darussalam": 153, "Cambodia": 154, "China PR": 155, "Guam": 157,
        "Hong Kong": 158, "India": 159, "Indonesia": 160, "Iran": 161, "Iraq": 162, "Japan": 163,
        "Jordan": 164, "Kazakhstan": 165, "Korea DPR": 166, "Korea Republic": 167, "Kuwait": 168,
        "Kyrgyzstan": 169, "Laos": 170, "Lebanon": 171, "Macau": 172, "Malaysia": 173,
        "Maldives": 174, "Mongolia": 175, "Myanmar": 176, "Nepal": 177, "Oman": 178,
        "Pakistan": 179, "Palestine": 180, "Philippines": 181, "Qatar": 182, "Saudi Arabia": 183,
        "Singapore": 184, "Sri Lanka": 185, "Syria": 186, "Tajikistan": 187, "Thailand": 188,
        "Turkmenistan": 189, "United Arab Emirates": 190, "Uzbekistan": 191, "Vietnam": 192,
        "Yemen": 193, "American Samoa": 194, "Australia": 195, "Cook Islands": 196, "Fiji": 197,
        "New Zealand": 198, "Papua New Guinea": 199, "Samoa": 200, "Solomon Islands": 201,
        "Tahiti": 202, "Tonga": 203, "Vanuatu": 204, "Gibraltar": 205, "Greenland": 206,
        "Dominican Republic": 207, "Estonia": 208, "Timor-Leste": 212, "Chinese Taipei": 213,
        "Comoros": 214, "New Caledonia": 215, "South Sudan": 218, "Kosovo": 219
    }

    print(f"Loaded {len(nation_mapping)} nations")
    return nation_mapping

    print("Parsing nation data")
    # Parse the nation data
    parts = nation_data.strip().split()
    i = 0
    while i < len(parts):
        try:
            if i + 1 < len(parts):
                # Try to extract name and ID
                if parts[i + 1].isdigit():
                    # Simple case: "Albania 1"
                    name = parts[i]
                    nation_id = int(parts[i + 1])
                    nation_mapping[name] = nation_id
                    i += 2
                else:
                    # Multi-word name case: "Bosnia and Herzegovina 8"
                    name = parts[i]
                    j = i + 1
                    # Keep adding words until we find a digit
                    while j < len(parts) and not parts[j].isdigit():
                        name += " " + parts[j]
                        j += 1

                    if j < len(parts) and parts[j].isdigit():
                        nation_id = int(parts[j])
                        nation_mapping[name] = nation_id

                    i = j + 1
            else:
                i += 1
        except Exception as e:
            print(f"Error parsing nation at position {i}: {e}")
            i += 1

    print(f"Loaded {len(nation_mapping)} nations")
    return nation_mapping


def get_existing_team_ids(teams_txt_path):
    """
    Scan teams.txt to get all existing team IDs.
    
    Args:
        teams_txt_path (str): Path to teams.txt file
    
    Returns:
        dict: Dictionary mapping team_id to team_name
    """
    existing_teams = {}
    if not teams_txt_path or not os.path.exists(teams_txt_path):
        return existing_teams
    
    try:
        file_encoding = detect_file_encoding(teams_txt_path)
        with open(teams_txt_path, 'r', encoding=file_encoding) as f:
            header_line = f.readline().strip()
            headers = header_line.split('\t')
            
            # Find teamid and teamname column indices
            teamid_idx = None
            teamname_idx = None
            for idx, col in enumerate(headers):
                if col.lower() == 'teamid':
                    teamid_idx = idx
                elif col.lower() == 'teamname':
                    teamname_idx = idx
            
            if teamid_idx is None:
                print("Warning: Could not find teamid column in teams.txt")
                return existing_teams
            
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) > teamid_idx:
                    try:
                        team_id = int(parts[teamid_idx])
                        team_name = parts[teamname_idx] if teamname_idx and len(parts) > teamname_idx else "Unknown"
                        existing_teams[team_id] = team_name
                    except (ValueError, IndexError):
                        continue
        
        print(f"Found {len(existing_teams)} existing teams in teams.txt")
    except Exception as e:
        print(f"Warning: Could not scan teams.txt for existing IDs: {e}")
    
    return existing_teams


def save_team_id_mappings(nation_team_ids, filepath):
    """
    Save nation to team ID mappings to a file.
    
    Args:
        nation_team_ids (dict): Dictionary of nation_name -> team_id
        filepath (str): Path to save the file
    
    Returns:
        bool: True if successful
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Nation Team ID Mappings\n")
            f.write("# Format: NationName,TeamID\n")
            f.write(f"# Saved: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("#" + "="*50 + "\n")
            for nation_name, team_id in nation_team_ids.items():
                f.write(f"{nation_name},{team_id}\n")
        print(f"Saved {len(nation_team_ids)} team ID mappings to {filepath}")
        return True
    except Exception as e:
        print(f"Error saving team ID mappings: {e}")
        return False


def load_team_id_mappings(filepath):
    """
    Load nation to team ID mappings from a file.
    
    Args:
        filepath (str): Path to the mappings file
    
    Returns:
        dict: Dictionary of nation_name -> team_id, or None if failed
    """
    try:
        nation_team_ids = {}
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        nation_name = parts[0].strip()
                        try:
                            team_id = int(parts[1].strip())
                            nation_team_ids[nation_name] = team_id
                        except ValueError:
                            continue
        print(f"Loaded {len(nation_team_ids)} team ID mappings from {filepath}")
        return nation_team_ids
    except Exception as e:
        print(f"Error loading team ID mappings: {e}")
        return None


def get_starting_xi_preview(players_txt_path, nation_id, nation_name):
    """
    Get a preview of the starting XI for a nation.
    
    Args:
        players_txt_path (str): Path to players.txt
        nation_id (int): The nation ID to filter by
        nation_name (str): Nation name for display
    
    Returns:
        str: Formatted string showing the starting XI preview
    """
    # Load blacklisted players
    blacklisted_players = load_blacklisted_players()
    
    players_by_position = {
        'GK': [],
        'DEF': [],
        'MID': [],
        'ATT': []
    }
    
    position_map = {
        0: 'GK',
        2: 'DEF', 3: 'DEF', 4: 'DEF', 5: 'DEF', 6: 'DEF', 7: 'DEF', 8: 'DEF',
        10: 'MID', 12: 'MID', 14: 'MID', 16: 'MID', 18: 'MID', 20: 'MID', 22: 'MID',
        23: 'ATT', 25: 'ATT', 27: 'ATT'
    }
    
    try:
        with open(players_txt_path, 'r', encoding='utf-16-le') as file:
            header_line = file.readline().strip()
            headers = header_line.split('\t')
            
            column_indices = {col.lower(): idx for idx, col in enumerate(headers)}
            
            playerid_idx = column_indices.get('playerid')
            nationality_idx = column_indices.get('nationality')
            gender_idx = column_indices.get('gender')
            position_idx = column_indices.get('preferredposition1')
            ovr_idx = column_indices.get('overallrating')
            firstname_idx = column_indices.get('firstname', -1)
            surname_idx = column_indices.get('surname', -1)
            
            if None in [playerid_idx, nationality_idx, gender_idx, position_idx, ovr_idx]:
                return f"Could not read player data for {nation_name}"
            
            for line in file:
                parts = line.strip().split('\t')
                if len(parts) <= max(playerid_idx, nationality_idx, gender_idx, position_idx, ovr_idx):
                    continue
                
                try:
                    player_id = int(parts[playerid_idx])
                    nationality = int(parts[nationality_idx])
                    gender = int(parts[gender_idx])
                    position = int(parts[position_idx])
                    ovr = int(parts[ovr_idx])
                    
                    if player_id in blacklisted_players or gender != 0 or nationality != nation_id:
                        continue
                    
                    firstname = parts[firstname_idx] if firstname_idx >= 0 and firstname_idx < len(parts) else ""
                    surname = parts[surname_idx] if surname_idx >= 0 and surname_idx < len(parts) else ""
                    name = f"{firstname} {surname}".strip() or f"Player {player_id}"
                    
                    pos_cat = position_map.get(position, 'MID')
                    players_by_position[pos_cat].append({
                        'name': name,
                        'ovr': ovr,
                        'id': player_id
                    })
                except (ValueError, IndexError):
                    continue
        
        # Sort by OVR and pick best players
        for pos in players_by_position:
            players_by_position[pos].sort(key=lambda x: -x['ovr'])
        
        # Build starting XI: 1 GK, 4 DEF, 3 MID, 3 ATT (4-3-3)
        starting_xi = []
        positions_needed = [('GK', 1), ('DEF', 4), ('MID', 3), ('ATT', 3)]
        
        preview = f"\n{'='*50}\nSTARTING XI PREVIEW: {nation_name}\n{'='*50}\n"
        
        for pos, count in positions_needed:
            available = players_by_position[pos][:count]
            preview += f"\n{pos}:\n"
            if available:
                for p in available:
                    preview += f"  - {p['name']} (OVR: {p['ovr']})\n"
                    starting_xi.append(p)
            else:
                preview += f"  - NO PLAYERS AVAILABLE\n"
            
            if len(available) < count:
                preview += f"  ⚠️ Need {count - len(available)} more {pos}\n"
        
        # Summary
        total_ovr = sum(p['ovr'] for p in starting_xi)
        avg_ovr = total_ovr / len(starting_xi) if starting_xi else 0
        preview += f"\n{'='*50}\n"
        preview += f"Team Average OVR: {avg_ovr:.1f}\n"
        preview += f"{'='*50}\n"
        
        return preview
        
    except Exception as e:
        return f"Error getting preview for {nation_name}: {e}"


def scan_nations_in_players_file(players_txt_path, nation_id_map, min_players=11, teams_txt_path=None):
    """
    Scan players.txt to count how many players are available per nation.
    Returns a dictionary with nation stats including player count and position breakdown.
    
    Args:
        players_txt_path (str): Path to the players.txt file
        nation_id_map (dict): Mapping of nation names to nation IDs
        min_players (int): Minimum players needed to show a nation (default 11)
        teams_txt_path (str): Path to teams.txt to check for already created teams
    
    Returns:
        dict: Dictionary with nation_id as key and stats dict as value
    """
    print(f"\nScanning players.txt for nation availability...")
    
    # Load blacklisted players
    blacklisted_players = load_blacklisted_players()
    
    # Blacklisted nations (already in the game - no need to create)
    blacklisted_nations = {
        "Argentina", "Croatia", "Czech Republic", "Czechia", "Denmark", "England",
        "Finland", "France", "Germany", "Ghana", "Hungary", "Iceland",
        "Republic of Ireland", "Ireland", "Israel", "Italy", "Mexico", "Morocco",
        "Holland", "Netherlands", "Northern Ireland", "Norway", "Poland", "Portugal",
        "Qatar", "Romania", "Scotland", "Spain", "Sweden", "Ukraine",
        "United States", "Wales"
    }
    print(f"Excluding {len(blacklisted_nations)} nations already in the base game")
    
    # Scan teams.txt for already created national teams (excluding women's teams)
    created_national_teams = set()
    if teams_txt_path and os.path.exists(teams_txt_path):
        try:
            file_encoding = detect_file_encoding(teams_txt_path)
            with open(teams_txt_path, 'r', encoding=file_encoding) as f:
                header_line = f.readline().strip()
                headers = header_line.split('\t')
                
                # Find teamname column index
                teamname_idx = None
                for idx, col in enumerate(headers):
                    if col.lower() == 'teamname':
                        teamname_idx = idx
                        break
                
                if teamname_idx is not None:
                    for line in f:
                        parts = line.strip().split('\t')
                        if len(parts) > teamname_idx:
                            team_name = parts[teamname_idx].strip()
                            # Skip women's national teams
                            if 'women' in team_name.lower():
                                continue
                            # Check if it looks like a national team (matches a nation name)
                            for nation_name in nation_id_map.keys():
                                if nation_name.lower() == team_name.lower() or \
                                   f"{nation_name} national" in team_name.lower() or \
                                   team_name.lower() == f"{nation_name.lower()} nt":
                                    created_national_teams.add(nation_name)
                                    break
            
            if created_national_teams:
                print(f"Found {len(created_national_teams)} national teams already in teams.txt: {', '.join(sorted(created_national_teams))}")
        except Exception as e:
            print(f"Warning: Could not scan teams.txt for existing teams: {e}")
    
    # Combine blacklisted nations with already created ones
    all_excluded_nations = blacklisted_nations | created_national_teams
    
    # Create reverse mapping (nation_id -> nation_name)
    nation_name_map = {v: k for k, v in nation_id_map.items()}
    
    # Dictionary to store nation stats
    nation_stats = {}
    
    try:
        with open(players_txt_path, 'r', encoding='utf-16-le') as file:
            # Read header line to determine column indices
            header_line = file.readline().strip()
            headers = header_line.split('\t')
            
            # Create mapping of column names to indices
            column_indices = {col.lower(): idx for idx, col in enumerate(headers)}
            
            # Check for required columns
            required_columns = ['playerid', 'nationality', 'gender', 'preferredposition1', 'overallrating']
            for col in required_columns:
                if col not in column_indices:
                    print(f"Error: Required column '{col}' not found in players.txt header.")
                    return {}
            
            # Get column indices
            playerid_idx = column_indices['playerid']
            nationality_idx = column_indices['nationality']
            gender_idx = column_indices['gender']
            position_idx = column_indices['preferredposition1']
            ovr_idx = column_indices['overallrating']
            
            # Position mapping for categorization
            position_categories = {
                0: 'GK',   # Goalkeeper
                2: 'DEF', 3: 'DEF', 4: 'DEF', 5: 'DEF', 6: 'DEF', 7: 'DEF', 8: 'DEF',  # Defenders
                10: 'MID', 12: 'MID', 14: 'MID', 16: 'MID',  # Midfielders
                18: 'MID', 20: 'MID', 22: 'MID',  # More midfielders
                23: 'ATT', 25: 'ATT', 27: 'ATT'  # Attackers
            }
            
            # Process each player
            for line in file:
                parts = line.strip().split('\t')
                if len(parts) <= max(playerid_idx, nationality_idx, gender_idx, position_idx, ovr_idx):
                    continue
                
                try:
                    player_id = int(parts[playerid_idx])
                    nationality = int(parts[nationality_idx])
                    gender = int(parts[gender_idx])
                    position = int(parts[position_idx])
                    ovr = int(parts[ovr_idx])
                    
                    # Skip blacklisted players and non-male players (gender 0 = male)
                    if player_id in blacklisted_players:
                        continue
                    if gender != 0:
                        continue
                    
                    # Initialize nation stats if not exists
                    if nationality not in nation_stats:
                        nation_stats[nationality] = {
                            'total': 0,
                            'GK': 0,
                            'DEF': 0,
                            'MID': 0,
                            'ATT': 0,
                            'avg_ovr': 0,
                            'ovr_sum': 0,
                            'top_ovr': 0
                        }
                    
                    # Update stats
                    nation_stats[nationality]['total'] += 1
                    nation_stats[nationality]['ovr_sum'] += ovr
                    nation_stats[nationality]['top_ovr'] = max(nation_stats[nationality]['top_ovr'], ovr)
                    
                    # Categorize by position
                    pos_cat = position_categories.get(position, 'MID')  # Default to MID if unknown
                    nation_stats[nationality][pos_cat] += 1
                    
                except (ValueError, IndexError):
                    continue
        
        # Calculate averages and filter by minimum players (excluding blacklisted nations)
        filtered_stats = {}
        skipped_base_game = []
        skipped_created = []
        for nation_id, stats in nation_stats.items():
            if stats['total'] >= min_players:
                stats['avg_ovr'] = round(stats['ovr_sum'] / stats['total'], 1) if stats['total'] > 0 else 0
                stats['name'] = nation_name_map.get(nation_id, f"Unknown ({nation_id})")
                stats['nation_id'] = nation_id
                
                # Check if nation is excluded
                if stats['name'] in blacklisted_nations:
                    skipped_base_game.append(stats['name'])
                    continue
                if stats['name'] in created_national_teams:
                    skipped_created.append(stats['name'])
                    continue
                    
                filtered_stats[nation_id] = stats
        
        if skipped_base_game:
            print(f"Skipped {len(skipped_base_game)} nations in base game")
        if skipped_created:
            print(f"Skipped {len(skipped_created)} nations already created: {', '.join(sorted(skipped_created))}")
        print(f"Found {len(filtered_stats)} nations available to create")
        return filtered_stats
        
    except Exception as e:
        print(f"Error scanning players.txt: {str(e)}")
        traceback.print_exc()
        return {}


def show_nation_availability_dialog(parent, nation_stats, nation_id_map):
    """
    Display a dialog showing available nations and their player counts.
    Allows user to select nations to create teams for.
    
    Args:
        parent: Parent tkinter window
        nation_stats (dict): Dictionary with nation stats from scan_nations_in_players_file
        nation_id_map (dict): Mapping of nation names to nation IDs
    
    Returns:
        list: List of selected nation names, or None if cancelled
    """
    if not nation_stats:
        messagebox.showinfo("No Nations Found", 
                           "No nations found with enough players.\n" +
                           "Make sure players.txt has players with valid nationalities.")
        return None
    
    # Sort nations by total players (descending)
    sorted_nations = sorted(nation_stats.values(), key=lambda x: (-x['total'], x['name']))
    
    # Create dialog
    dialog = tk.Toplevel(parent)
    dialog.title("Available Nations for National Teams")
    dialog.geometry("700x600")
    dialog.attributes('-topmost', True)
    dialog.update()
    
    # Instructions
    label = tk.Label(dialog, text="Nations with enough players to create national teams:\n" +
                                  "(Select nations and click 'Create Selected Teams' or 'Export List')",
                     font=('Arial', 10))
    label.pack(pady=10)
    
    # Stats summary
    total_nations = len(sorted_nations)
    viable_nations = len([n for n in sorted_nations if n['total'] >= 23])
    summary_label = tk.Label(dialog, 
                             text=f"Total: {total_nations} nations | Viable (23+ players): {viable_nations}",
                             font=('Arial', 9, 'bold'))
    summary_label.pack(pady=5)
    
    # Filter frame
    filter_frame = tk.Frame(dialog)
    filter_frame.pack(fill=tk.X, padx=10, pady=5)
    
    tk.Label(filter_frame, text="Min players:").pack(side=tk.LEFT)
    min_var = tk.StringVar(value="11")
    min_entry = tk.Entry(filter_frame, textvariable=min_var, width=5)
    min_entry.pack(side=tk.LEFT, padx=5)
    
    # Create scrollable frame with listbox
    list_frame = tk.Frame(dialog)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    scrollbar = tk.Scrollbar(list_frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # Create listbox with extended selection
    listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, 
                         yscrollcommand=scrollbar.set, font=('Courier', 9))
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.config(command=listbox.yview)
    
    # Store nation names for reference
    nation_names_list = []
    
    def populate_list(min_players=11):
        """Populate the listbox with filtered nations"""
        listbox.delete(0, tk.END)
        nation_names_list.clear()
        
        for stats in sorted_nations:
            if stats['total'] >= min_players:
                # Format: "Nation Name          | Total: XX | GK: X | DEF: XX | MID: XX | ATT: XX | Avg: XX"
                line = f"{stats['name']:<25} | Total: {stats['total']:>3} | GK: {stats['GK']:>2} | DEF: {stats['DEF']:>2} | MID: {stats['MID']:>2} | ATT: {stats['ATT']:>2} | Avg: {stats['avg_ovr']:>4}"
                
                # Add indicator for viability
                if stats['total'] >= 23 and stats['GK'] >= 2:
                    line = "✓ " + line
                elif stats['total'] >= 11 and stats['GK'] >= 1:
                    line = "○ " + line
                else:
                    line = "✗ " + line
                
                listbox.insert(tk.END, line)
                nation_names_list.append(stats['name'])
    
    def apply_filter():
        try:
            min_players = int(min_var.get())
            populate_list(min_players)
        except ValueError:
            populate_list(11)
    
    filter_btn = tk.Button(filter_frame, text="Filter", command=apply_filter)
    filter_btn.pack(side=tk.LEFT, padx=10)
    
    # Legend
    legend_label = tk.Label(dialog, 
                           text="✓ = Viable (23+ players, 2+ GK) | ○ = Possible (11+ players, 1+ GK) | ✗ = Needs more players/GK",
                           font=('Arial', 8))
    legend_label.pack(pady=5)
    
    # Result variables
    result = {'selected': None, 'action': None}
    
    def on_create():
        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select at least one nation.")
            return
        result['selected'] = [nation_names_list[i] for i in selected_indices]
        result['action'] = 'create'
        dialog.destroy()
    
    def on_export():
        # Export full list to a text file
        export_path = filedialog.asksaveasfilename(
            title="Save Nation List",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if export_path:
            try:
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write("=" * 80 + "\n")
                    f.write("NATIONAL TEAM AVAILABILITY REPORT\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Total nations with 11+ players: {len(sorted_nations)}\n")
                    f.write(f"Viable nations (23+ players, 2+ GK): {len([n for n in sorted_nations if n['total'] >= 23 and n['GK'] >= 2])}\n\n")
                    f.write("-" * 80 + "\n")
                    f.write(f"{'Nation':<25} | {'Total':>5} | {'GK':>3} | {'DEF':>3} | {'MID':>3} | {'ATT':>3} | {'Avg OVR':>7} | {'Top OVR':>7}\n")
                    f.write("-" * 80 + "\n")
                    
                    for stats in sorted_nations:
                        f.write(f"{stats['name']:<25} | {stats['total']:>5} | {stats['GK']:>3} | {stats['DEF']:>3} | {stats['MID']:>3} | {stats['ATT']:>3} | {stats['avg_ovr']:>7} | {stats['top_ovr']:>7}\n")
                    
                    f.write("-" * 80 + "\n")
                    f.write("\n\nNations ready for batch import (copy these lines):\n")
                    f.write("-" * 40 + "\n")
                    for stats in sorted_nations:
                        if stats['total'] >= 23 and stats['GK'] >= 2:
                            f.write(f"{stats['name']}\n")
                
                messagebox.showinfo("Export Complete", f"Nation list exported to:\n{export_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def on_cancel():
        result['action'] = 'cancel'
        dialog.destroy()
    
    # Buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(fill=tk.X, padx=10, pady=10)
    
    tk.Button(button_frame, text="Create Selected Teams", command=on_create, 
              bg='green', fg='white').pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Export List", command=on_export).pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=5)
    
    # Select all viable nations button
    def select_viable():
        listbox.selection_clear(0, tk.END)
        for i, name in enumerate(nation_names_list):
            stats = nation_stats.get(nation_id_map.get(name))
            if stats and stats['total'] >= 23 and stats['GK'] >= 2:
                listbox.selection_set(i)
    
    tk.Button(button_frame, text="Select All Viable", command=select_viable).pack(side=tk.LEFT, padx=5)
    
    # Initial population
    populate_list(11)
    
    # Wait for dialog to close
    dialog.transient(parent)
    dialog.grab_set()
    parent.wait_window(dialog)
    
    return result


def select_nations_dialog(parent, nation_names):
    """Create a dialog to select multiple nations"""
    print("Opening nation selection dialog")
    dialog = tk.Toplevel(parent)
    dialog.title("Select Nations")
    dialog.geometry("400x500")
    dialog.attributes('-topmost', True)  # Make sure dialog stays on top
    dialog.update()  # Update to ensure it's drawn

    # Add a label with instructions
    label = tk.Label(dialog, text="Select nations and click OK")
    label.pack(pady=5)

    # Add a scrollbar and listbox
    frame = tk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, yscrollcommand=scrollbar.set)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar.config(command=listbox.yview)

    # Add nations to the listbox
    for nation in nation_names:
        listbox.insert(tk.END, nation)

    print(f"Added {len(nation_names)} nations to selection dialog")

    # Variables to store the result
    selected_nations = []
    dialog_completed = False

    # Function to handle selection
    def on_ok():
        nonlocal selected_nations, dialog_completed
        selected_indices = listbox.curselection()
        print(f"Selected indices: {selected_indices}")
        selected_nations = [nation_names[i] for i in selected_indices]
        print(f"Selected nations: {selected_nations}")
        dialog_completed = True
        dialog.destroy()

    def on_cancel():
        nonlocal dialog_completed
        print("Nation selection canceled")
        dialog_completed = True
        dialog.destroy()

    # Add buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=10)

    cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(side=tk.RIGHT, padx=10)

    ok_button = tk.Button(button_frame, text="OK", command=on_ok)
    ok_button.pack(side=tk.RIGHT, padx=10)

    # Make OK button default (respond to Enter key)
    ok_button.focus_set()
    dialog.bind('<Return>', lambda event: on_ok())

    # Ensure the window is shown and interactive
    dialog.deiconify()  # Make sure dialog is not minimized
    dialog.lift()  # Lift above other windows
    dialog.focus_force()  # Force focus
    dialog.grab_set()  # Make modal

    print("Waiting for user selection")

    # Handle window close event
    def on_close():
        nonlocal dialog_completed
        print("Dialog closed by user")
        dialog_completed = True
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)

    # Safety timeout in case dialog is not visible
    def check_dialog():
        if not dialog_completed and dialog.winfo_exists():
            print("Dialog still waiting for user input...")
            dialog.after(5000, check_dialog)  # Check again in 5 seconds

    dialog.after(5000, check_dialog)  # Initial check in 5 seconds

    # Make the dialog modal
    dialog.transient(parent)
    parent.wait_window(dialog)

    if not dialog_completed:
        print("Dialog wasn't completed normally!")

    print(f"Dialog closed, returned {len(selected_nations)} nations")
    return selected_nations


def load_formations():
    """Load the predefined formation data from FIFA"""
    formations = [
        {"id": 785, "name": "3-1-4-2", "audio_id": 1, "fullname_id": 28},
        {"id": 848, "name": "3-4-1-2", "audio_id": 1, "fullname_id": 29},
        {"id": 720, "name": "3-4-2-1", "audio_id": 19, "fullname_id": 21},
        {"id": 823, "name": "3-4-3", "audio_id": 0, "fullname_id": 2},
        {"id": 845, "name": "3-5-2", "audio_id": 1, "fullname_id": 22},
        {"id": 733, "name": "4-1-2-1-2", "audio_id": 11, "fullname_id": 9},
        {"id": 215, "name": "4-1-3-2", "audio_id": 12, "fullname_id": 30},
        {"id": 834, "name": "4-1-4-1", "audio_id": 15, "fullname_id": 31},
        {"id": 761, "name": "4-2-1-3", "audio_id": 18, "fullname_id": 27},
        {"id": 624, "name": "4-2-2-2", "audio_id": 10, "fullname_id": 32},
        {"id": 841, "name": "4-2-3-1", "audio_id": 14, "fullname_id": 16},
        {"id": 755, "name": "4-2-4", "audio_id": 2, "fullname_id": 33},
        {"id": 746, "name": "4-3-1-2", "audio_id": 9, "fullname_id": 34},
        {"id": 604, "name": "4-3-2-1", "audio_id": 8, "fullname_id": 20},
        {"id": 849, "name": "4-3-3", "audio_id": 6, "fullname_id": 7},
        {"id": 656, "name": "4-4-1-1", "audio_id": 14, "fullname_id": 18},
        {"id": 842, "name": "4-4-2", "audio_id": 10, "fullname_id": 11},
        {"id": 808, "name": "4-5-1", "audio_id": 15, "fullname_id": 19},
        {"id": 567, "name": "5-2-1-2", "audio_id": 4, "fullname_id": 35},
        {"id": 846, "name": "5-2-3", "audio_id": 3, "fullname_id": 36},
        {"id": 843, "name": "5-3-2", "audio_id": 4, "fullname_id": 24},
        {"id": 686, "name": "5-4-1", "audio_id": 5, "fullname_id": 14},
    ]

    # Formation data from the provided file
    formation_data = {
        "3-1-4-2": {
            "offset6x": "0.65", "offset5y": "0.5875", "offset10x": "0.39", "offset2x": "0.5", "defenders": "3.5",
            "offset2y": "0.15", "offset6y": "0.5125", "offset7x": "0.35", "offset3x": "0.325", "offset8x": "0.075",
            "offset10y": "0.875", "offset3y": "0.15", "offset4x": "0.5", "offset7y": "0.5125", "offset0x": "0.5",
            "offset8y": "0.5875", "attackers": "2", "offset9x": "0.6", "midfielders": "4.5", "offset5x": "0.925",
            "offset0y": "0.0175", "offset1x": "0.675", "offset4y": "0.3375", "offset9y": "0.875", "offset1y": "0.15",
            "pos0role": "4161", "pos6role": "21445", "pos8role": "25602", "pos4role": "17089", "pos7role": "21185",
            "pos2role": "12737", "pos1role": "12737", "pos10role": "38275", "pos3role": "12737", "pos9role": "38341",
            "pos5role": "25730", "position10": "26", "position6": "13", "position8": "16", "position5": "12",
            "position2": "5", "position4": "10", "position3": "6", "position0": "0", "position9": "24",
            "position7": "15", "position1": "4", "defensivedepth": "50", "buildupplay": "2"
        },
        "3-4-1-2": {
            "offset6x": "0.35", "offset5y": "0.5125", "offset10x": "0.39", "offset2x": "0.5", "defenders": "3",
            "offset2y": "0.15", "offset6y": "0.5125", "offset7x": "0.075", "offset3x": "0.325", "offset8x": "0.5",
            "offset10y": "0.875", "offset3y": "0.15", "offset4x": "0.925", "offset7y": "0.5875", "offset0x": "0.5",
            "offset8y": "0.6625", "attackers": "2.5", "offset9x": "0.6", "midfielders": "4.5", "offset5x": "0.65",
            "offset0y": "0.0175", "offset1x": "0.675", "offset4y": "0.5875", "offset9y": "0.875", "offset1y": "0.15",
            "pos0role": "4161", "pos6role": "21314", "pos8role": "29570", "pos4role": "25602", "pos7role": "25602",
            "pos2role": "12737", "pos1role": "12802", "pos10role": "38405", "pos3role": "12737", "pos9role": "38405",
            "pos5role": "21314", "position10": "26", "position6": "15", "position8": "18", "position5": "13",
            "position2": "5", "position4": "12", "position3": "6", "position0": "0", "position9": "24",
            "position7": "16", "position1": "4", "defensivedepth": "30", "buildupplay": "3"
        },
        "4-3-3": {
            "offset6x": "0.65", "offset5y": "0.3375", "offset10x": "0.075", "offset2x": "0.6731", "defenders": "4",
            "offset2y": "0.1537", "offset6y": "0.5125", "offset7x": "0.35", "offset3x": "0.325", "offset8x": "0.925",
            "offset10y": "0.825", "offset3y": "0.15", "offset4x": "0.075", "offset7y": "0.5125", "offset0x": "0.497",
            "offset8y": "0.825", "attackers": "3", "offset9x": "0.4995", "midfielders": "3", "offset5x": "0.5",
            "offset0y": "0.0175", "offset1x": "0.9", "offset4y": "0.2", "offset9y": "0.875", "offset1y": "0.175",
            "pos0role": "4161", "pos6role": "21314", "pos8role": "33794", "pos4role": "8386", "pos7role": "21314",
            "pos2role": "12737", "pos1role": "8386", "pos10role": "33794", "pos3role": "12737", "pos9role": "38405",
            "pos5role": "17089", "position10": "27", "position6": "13", "position8": "23", "position5": "10",
            "position2": "4", "position4": "7", "position3": "6", "position0": "0", "position9": "25",
            "position7": "15", "position1": "3", "defensivedepth": "50", "buildupplay": "2"
        },
        "4-4-2": {
            "offset6x": "0.65", "offset5y": "0.5875", "offset10x": "0.39", "offset2x": "0.675", "defenders": "4",
            "offset2y": "0.15", "offset6y": "0.5125", "offset7x": "0.35", "offset3x": "0.325", "offset8x": "0.075",
            "offset10y": "0.875", "offset3y": "0.15", "offset4x": "0.075", "offset7y": "0.5125", "offset0x": "0.5",
            "offset8y": "0.5875", "attackers": "2", "offset9x": "0.6", "midfielders": "4", "offset5x": "0.925",
            "offset0y": "0.0175", "offset1x": "0.925", "offset4y": "0.2", "offset9y": "0.875", "offset1y": "0.2",
            "pos0role": "4226", "pos6role": "21381", "pos8role": "25794", "pos4role": "8513", "pos7role": "21314",
            "pos2role": "12802", "pos1role": "8450", "pos10role": "38213", "pos3role": "12737", "pos9role": "38341",
            "pos5role": "25794", "position10": "26", "position6": "13", "position8": "16", "position5": "12",
            "position2": "4", "position4": "7", "position3": "6", "position0": "0", "position9": "24",
            "position7": "15", "position1": "3", "defensivedepth": "50", "buildupplay": "3"
        }
    }

    # Add the full formation data to each formation
    for formation in formations:
        name = formation["name"]
        if name in formation_data:
            formation.update(formation_data[name])

    return formations


def select_formation_dialog(parent, formations):
    """Create a dialog to select a formation with improved focus handling"""
    print("Opening formation selection dialog")
    dialog = tk.Toplevel(parent)
    dialog.title("Select Formation")
    dialog.geometry("300x400")

    # Position the dialog in the center of the screen
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    x = (screen_width - 300) // 2
    y = (screen_height - 400) // 2
    dialog.geometry(f"300x400+{x}+{y}")

    # Make sure dialog stays on top
    dialog.attributes('-topmost', True)
    dialog.grab_set()  # Make modal - prevents clicking elsewhere

    # Add a label with instructions
    label = tk.Label(dialog, text="Select a formation and click OK")
    label.pack(pady=5)

    # Add a scrollbar and listbox
    frame = tk.Frame(dialog)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = tk.Listbox(frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar.config(command=listbox.yview)

    # Add formations to the listbox
    for i, formation in enumerate(formations):
        listbox.insert(tk.END, formation["name"])
        # Pre-select the 4-3-3 formation as default
        if formation["name"] == "4-3-3":
            listbox.selection_set(i)

    print(f"Added {len(formations)} formations to selection dialog")

    # Variables to store the result
    selected_formation = None

    # Default to 4-3-3 in case dialog is closed unexpectedly
    default_formation = next((f for f in formations if f["name"] == "4-3-3"), formations[0])

    # Function to handle selection
    def on_ok():
        nonlocal selected_formation
        selected_indices = listbox.curselection()
        if selected_indices:
            selected_index = selected_indices[0]
            # Create a deep copy of the selected formation to avoid modifying the original
            formation_dict = formations[selected_index].copy()

            # Store its original ID but don't use it for the new formation
            original_id = formation_dict.get('id', 'unknown')
            formation_dict['original_id'] = original_id

            # We'll generate a new ID when we write to the file
            print(f"Selected formation: {formation_dict['name']} (original ID: {original_id})")
            selected_formation = formation_dict
        else:
            # If nothing selected, default to 4-3-3
            selected_formation = default_formation.copy()
            original_id = selected_formation.get('id', 'unknown')
            selected_formation['original_id'] = original_id
            print(f"No selection made, defaulting to: {selected_formation['name']} (original ID: {original_id})")
        dialog.destroy()

    def on_cancel():
        nonlocal selected_formation
        # Default to 4-3-3 on cancel
        selected_formation = default_formation.copy()
        original_id = selected_formation.get('id', 'unknown')
        selected_formation['original_id'] = original_id
        print(f"Formation selection canceled, defaulting to: {selected_formation['name']} (original ID: {original_id})")
        dialog.destroy()

    # Handle dialog close via X button
    dialog.protocol("WM_DELETE_WINDOW", on_cancel)

    # Add buttons
    button_frame = tk.Frame(dialog)
    button_frame.pack(fill=tk.X, pady=10)

    cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(side=tk.RIGHT, padx=10)

    ok_button = tk.Button(button_frame, text="OK", command=on_ok)
    ok_button.pack(side=tk.RIGHT, padx=10)

    # Ensure dialog is visible and has focus
    dialog.update()
    dialog.deiconify()
    dialog.lift()
    dialog.focus_force()

    # Make OK button default (respond to Enter key)
    ok_button.focus_set()
    dialog.bind('<Return>', lambda event: on_ok())

    # wait_window will block until the dialog is destroyed
    parent.wait_window(dialog)

    # Always return a formation, even if dialog was closed unexpectedly
    if selected_formation is None:
        selected_formation = default_formation.copy()
        original_id = selected_formation.get('id', 'unknown')
        selected_formation['original_id'] = original_id
        print(f"Dialog closed abnormally, defaulting to: {selected_formation['name']} (original ID: {original_id})")

    return selected_formation


def create_national_teams_from_file(file_path, input_dir, players_txt_path, nation_id_map, formations=None):
    """
    Create multiple national teams from a text file where each line has a national team name and team ID

    Args:
        file_path (str): Path to the text file containing team names and IDs
        input_dir (str): Directory containing all game files
        players_txt_path (str): Path to players.txt file for national teams
        nation_id_map (dict): Mapping of nation names to nation IDs
        formations (list, optional): List of available formations

    Returns:
        tuple: (success_count, total_count) - Number of teams successfully created and total attempted
    """
    print(f"\nReading national teams from file: {file_path}")

    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return 0, 0

    # Variables to track teams
    team_list = []
    team_ids = {}

    # Read the file line by line
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                line = line.strip()

                # Skip empty lines or comments
                if not line or line.startswith('#'):
                    continue

                # Parse the line to get team name and ID
                parts = line.split(',')
                if len(parts) != 2:
                    print(f"Warning: Invalid format at line {line_num}: {line}")
                    print("Expected format: NationName,TeamID")
                    continue

                team_name = parts[0].strip()
                team_id_str = parts[1].strip()

                # Validate team ID
                try:
                    team_id = int(team_id_str)
                except ValueError:
                    print(f"Warning: Invalid team ID at line {line_num}: {team_id_str}")
                    continue

                # Check if the nation exists in our mapping
                if team_name not in nation_id_map:
                    # Try to find a partial match
                    matching_nations = [n for n in nation_id_map.keys() if team_name.lower() in n.lower()]
                    if matching_nations:
                        original_name = team_name
                        team_name = matching_nations[0]
                        print(f"Note: Matched '{original_name}' to '{team_name}'")
                    else:
                        print(f"Warning: Nation '{team_name}' not found in nation ID mapping. Skipping.")
                        continue

                # Add to our list
                team_list.append(team_name)
                team_ids[team_name] = team_id
                print(f"Added team: {team_name} (ID: {team_id})")

        print(f"Found {len(team_list)} valid teams in the file")

        if not team_list:
            print("No valid teams found in the file. Nothing to process.")
            return 0, 0

        # Ask user to select a formation (same for all teams)
        if formations:
            # Get the default 4-3-3 formation
            default_formation = next((f for f in formations if f["name"] == "4-3-3"), formations[0])
            selected_formation = select_formation_dialog(tk.Tk(), formations)
            if not selected_formation:
                selected_formation = default_formation
        else:
            selected_formation = None

        # Process each team
        success_count = 0
        for team_name in team_list:
            team_id = team_ids[team_name]
            nation_id = nation_id_map.get(team_name)

            print(f"\nProcessing national team: {team_name} (ID: {team_id}, Nation ID: {nation_id})")

            # Create a team appender for this national team
            appender = TeamAppender(team_name, team_id, 78, nation_id, is_national_team=True)

            # Load player data from players.txt
            if not appender.load_player_data(players_txt_path):
                print(f"Failed to load player data for {team_name}. Skipping.")
                continue

            # Process all files
            if appender.process_files(input_dir, selected_formation):
                success_count += 1
                print(f"Team {team_name} processed successfully.")
            else:
                print(f"Some errors occurred while processing team {team_name}.")

        return success_count, len(team_list)

    except Exception as e:
        print(f"Error processing teams file: {str(e)}")
        traceback.print_exc()
        return 0, 0


# Add to TeamAppender class:
def append_to_formations_file(self, file_path, selected_formation=None):
    """Append formation to the formations.txt file"""
    try:
        if os.path.exists(file_path):
            # Parse the header to understand the file structure
            header_dict = self.parse_file_header(file_path, "formations")

            # Get the next formation ID from the correct column
            formationid_idx = header_dict.get('formationid')
            if formationid_idx is not None:
                next_formation_id = self.get_highest_id_from_file(file_path, formationid_idx, 1) + 1
                print(f"Found formationid at column {formationid_idx}, next ID: {next_formation_id}")
            else:
                next_formation_id = 2
                print(f"Could not find formationid column, using default: {next_formation_id}")

            # Read the entire content to keep it
            with open(file_path, 'r', encoding='utf-16-le') as file:
                content = file.read()

            # If user selected a specific formation, use that data
            if selected_formation:
                # Create a copy of the formation data to avoid modifying the original
                formation_data = selected_formation.copy()
                # Ensure we're using our new formation ID, not the original one
                print(
                    f"Using formation {formation_data.get('name', '4-3-3')} with NEW ID: {next_formation_id} (original ID was: {formation_data.get('id', 'N/A')})")

                # Build the formation template using the formation data
                formations_template = (
                    f"{formation_data.get('offset6x', '0.65')}\t"
                    f"{formation_data.get('offset5y', '0.3375')}\t"
                    f"{formation_data.get('offset10x', '0.075')}\t"
                    f"{formation_data.get('offset2x', '0.6731')}\t"
                    f"{formation_data.get('defenders', '4')}\t"
                    f"{formation_data.get('offset2y', '0.1537')}\t"
                    f"{formation_data.get('offset6y', '0.5125')}\t"
                    f"{formation_data.get('offset7x', '0.35')}\t"
                    f"{formation_data.get('offset3x', '0.325')}\t"
                    f"{formation_data.get('offset8x', '0.925')}\t"
                    f"{formation_data.get('offset10y', '0.825')}\t"
                    f"{formation_data.get('offset3y', '0.15')}\t"
                    f"{formation_data.get('offset4x', '0.075')}\t"
                    f"{formation_data.get('offset7y', '0.5125')}\t"
                    f"{formation_data.get('offset0x', '0.497')}\t"
                    f"{formation_data.get('offset8y', '0.825')}\t"
                    f"{formation_data.get('attackers', '3')}\t"
                    f"{formation_data.get('offset9x', '0.4995')}\t"
                    f"{formation_data.get('midfielders', '3')}\t"
                    f"{formation_data.get('offset5x', '0.5')}\t"
                    f"{formation_data.get('offset0y', '0.0175')}\t"
                    f"{formation_data.get('offset1x', '0.9')}\t"
                    f"{formation_data.get('offset4y', '0.2')}\t"
                    f"{formation_data.get('offset9y', '0.875')}\t"
                    f"{formation_data.get('offset1y', '0.175')}\t"
                    f"{formation_data.get('pos0role', '4161')}\t"
                    f"{formation_data.get('pos6role', '21314')}\t"
                    f"{formation_data.get('pos8role', '33794')}\t"
                    f"{formation_data.get('pos4role', '8386')}\t"
                    f"{formation_data.get('pos7role', '21314')}\t"
                    f"{formation_data.get('pos2role', '12737')}\t"
                    f"{formation_data.get('pos1role', '8386')}\t"
                    f"{formation_data.get('pos10role', '33794')}\t"
                    f"{formation_data.get('pos3role', '12737')}\t"
                    f"{formation_data.get('pos9role', '12737')}\t"
                    f"{formation_data.get('pos5role', '17089')}\t"
                    f"{formation_data.get('name', '4-3-3')}\t"
                    f"{formation_data.get('position10', '27')}\t"
                    f"{formation_data.get('position6', '13')}\t"
                    f"{formation_data.get('offensiverating', '3')}\t"
                    f"{formation_data.get('position8', '23')}\t"
                    f"{formation_data.get('position5', '10')}\t"
                    f"{formation_data.get('audio_id', '6')}\t"
                    f"{self.team_id}\t"
                    f"{formation_data.get('position2', '4')}\t"
                    f"{next_formation_id}\t"  # ALWAYS use our new incremented ID here
                    f"{formation_data.get('relativeformationid', '9')}\t"
                    f"{formation_data.get('position4', '7')}\t"
                    f"{formation_data.get('position3', '6')}\t"
                    f"{formation_data.get('fullname_id', '7')}\t"
                    f"{formation_data.get('position0', '0')}\t"
                    f"{formation_data.get('position9', '25')}\t"
                    f"{formation_data.get('position7', '15')}\t"
                    f"{formation_data.get('position1', '3')}"
                )
            else:
                # Template structure for 4-3-3 formation with updated IDs
                formations_template = f"""0.65\t0.3375\t0.075\t0.6731\t4\t0.1537\t0.5125\t0.35\t0.325\t0.925\t0.825\t0.15\t0.075\t0.5125\t0.497\t0.825\t3\t0.4995\t3\t0.5\t0.0175\t0.9\t0.2\t0.875\t0.175\t4161\t21314\t33794\t8386\t21314\t12737\t8386\t33794\t12737\t12737\t17089\t4-3-3\t27\t13\t3\t23\t10\t6\t{self.team_id}\t4\t{next_formation_id}\t9\t7\t6\t7\t0\t25\t15\t3"""

            # Ensure there's a newline at the end of the original content
            if content and not content.endswith('\n'):
                content += '\n'

            # Append the new formation to the content and write back
            with open(file_path, 'w', encoding='utf-16-le') as file:
                file.write(content + formations_template)

            print(f"✓ Added formation to file: {file_path}")
            return True
        else:
            print(f"✗ Formations file not found: {file_path}")
            return False
    except Exception as e:
        print(f"✗ Error appending to formations file: {str(e)}")
        traceback.print_exc()
        return False


def main():
    # Create a Tkinter root window (will not be shown)
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Open a dialog for the user to select the folder containing your game files
    input_dir = filedialog.askdirectory(title="Select the folder with game files")

    if not input_dir:
        messagebox.showerror("Error", "No folder selected. Exiting.")
        return

    # Display the selected folder in the console
    print("Selected folder:", input_dir)

    # Check if teams.txt exists in that folder
    teams_file = os.path.join(input_dir, "teams.txt")
    if not os.path.exists(teams_file):
        print("teams.txt not found in", input_dir)
        messagebox.showerror("Error", "teams.txt not found in the selected folder. Please select the correct folder.")
        return

    # Ask if creating national teams
    is_national_teams = messagebox.askyesno("Team Creator",
                                            "Are you creating national teams?\n\n" +
                                            "Yes - Create NATIONAL teams using players.txt\n" +
                                            "No - Create CLUB teams using player files")

    if is_national_teams:
        print("Selected national team option")

        # Load nation ID mapping
        try:
            nation_id_map = load_nation_id_mapping()
            print(f"Loaded {len(nation_id_map)} nations")
            if not nation_id_map:
                messagebox.showerror("Error", "Failed to load nation ID mapping.")
                root.destroy()
                return
        except Exception as e:
            messagebox.showerror("Error", f"Error loading nation ID mapping: {str(e)}")
            traceback.print_exc()
            root.destroy()
            return

        # Ask user to select players.txt file
        messagebox.showinfo("National Team Creator", "Please select the players.txt file.")

        players_txt_path = filedialog.askopenfilename(
            title="Select players.txt File",
            filetypes=[("TXT files", "*.txt"), ("All files", "*.*")]
        )

        if not players_txt_path:
            messagebox.showerror("Error", "No players.txt file selected. Exiting.")
            root.destroy()
            return

        # Verify the file can be opened
        try:
            with open(players_txt_path, 'r', encoding='utf-16-le') as test_file:
                first_line = test_file.readline()
                print(f"Successfully read players.txt: {first_line[:50]}...")
        except Exception as e:
            messagebox.showerror("Error", f"Unable to read players.txt: {str(e)}")
            traceback.print_exc()
            root.destroy()
            return

        # Load formations data
        formations = load_formations()

        # Ask which mode to use for national team creation - use messagebox which works with hidden root
        scan_first = messagebox.askyesno(
            "National Team Creator",
            "Would you like to SCAN which nations have enough players first?\n\n" +
            "Yes - Scan players.txt to see available nations\n" +
            "No - Skip scanning and create teams directly")
        
        if scan_first:
            national_team_mode = 'scan'
        else:
            # Ask between batch and interactive
            use_batch = messagebox.askyesno(
                "National Team Creator",
                "How would you like to create national teams?\n\n" +
                "Yes - Import from a text file (batch mode)\n" +
                "No - Create teams one by one (interactive mode)")
            
            if use_batch:
                national_team_mode = 'batch'
            else:
                national_team_mode = 'interactive'

        if national_team_mode == 'scan':
            # Scan mode - show available nations
            print("\n" + "="*60)
            print("SCANNING PLAYERS.TXT FOR AVAILABLE NATIONS...")
            print("="*60)
            teams_txt_path = os.path.join(input_dir, "teams.txt")
            nation_stats = scan_nations_in_players_file(players_txt_path, nation_id_map, min_players=11, teams_txt_path=teams_txt_path)
            
            if not nation_stats:
                messagebox.showerror("Error", "No nations found with enough players.")
                root.destroy()
                return
            
            # Sort nations by total players
            sorted_nations = sorted(nation_stats.values(), key=lambda x: (-x['total'], x['name']))
            
            # Print results to console
            print("\n" + "="*80)
            print("AVAILABLE NATIONS FOR NATIONAL TEAMS")
            print("="*80)
            print(f"{'Nation':<25} | {'Total':>5} | {'GK':>3} | {'DEF':>3} | {'MID':>3} | {'ATT':>3} | {'Avg':>5} | Status")
            print("-"*80)
            
            viable_nations = []
            possible_nations = []
            
            for stats in sorted_nations:
                status = ""
                if stats['total'] >= 23 and stats['GK'] >= 2:
                    status = "✓ VIABLE"
                    viable_nations.append(stats['name'])
                elif stats['total'] >= 11 and stats['GK'] >= 1:
                    status = "○ POSSIBLE"
                    possible_nations.append(stats['name'])
                else:
                    status = "✗ NEEDS MORE"
                
                print(f"{stats['name']:<25} | {stats['total']:>5} | {stats['GK']:>3} | {stats['DEF']:>3} | {stats['MID']:>3} | {stats['ATT']:>3} | {stats['avg_ovr']:>5} | {status}")
            
            print("-"*80)
            print(f"\nSUMMARY: {len(viable_nations)} viable nations, {len(possible_nations)} possible nations")
            print(f"Viable nations (23+ players, 2+ GK): {', '.join(viable_nations[:10])}{'...' if len(viable_nations) > 10 else ''}")
            print("="*80 + "\n")
            
            # Show summary message
            messagebox.showinfo("Scan Complete", 
                f"Found {len(viable_nations)} viable nations (23+ players, 2+ GK)\n" +
                f"Found {len(possible_nations)} possible nations (11-22 players)\n\n" +
                "Check the console/terminal for the full list!")
            
            # Ask user what to do - use yes/no questions
            if viable_nations:
                create_all = messagebox.askyesno(
                    "Create Teams",
                    f"Do you want to create ALL {len(viable_nations)} viable national teams?\n\n" +
                    "Yes - Create all viable nations\n" +
                    "No - Choose other options (export/specific nations)")
                
                if create_all:
                    selected_nations = viable_nations
                    print(f"Selected all {len(selected_nations)} viable nations")
                else:
                    # Ask about export
                    do_export = messagebox.askyesno(
                        "Export List",
                        "Do you want to export the nation list to a file?\n\n" +
                        "Yes - Save list to text file\n" +
                        "No - Enter specific nations to create")
                    
                    if do_export:
                        # Export to file
                        export_path = filedialog.asksaveasfilename(
                            title="Save Nation List",
                            defaultextension=".txt",
                            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                        )
                        if export_path:
                            try:
                                with open(export_path, 'w', encoding='utf-8') as f:
                                    f.write("=" * 80 + "\n")
                                    f.write("NATIONAL TEAM AVAILABILITY REPORT\n")
                                    f.write("=" * 80 + "\n\n")
                                    f.write(f"Total nations with 11+ players: {len(sorted_nations)}\n")
                                    f.write(f"Viable nations (23+ players, 2+ GK): {len(viable_nations)}\n\n")
                                    f.write("-" * 80 + "\n")
                                    f.write(f"{'Nation':<25} | {'Total':>5} | {'GK':>3} | {'DEF':>3} | {'MID':>3} | {'ATT':>3} | {'Avg OVR':>7}\n")
                                    f.write("-" * 80 + "\n")
                                    
                                    for stats in sorted_nations:
                                        f.write(f"{stats['name']:<25} | {stats['total']:>5} | {stats['GK']:>3} | {stats['DEF']:>3} | {stats['MID']:>3} | {stats['ATT']:>3} | {stats['avg_ovr']:>7}\n")
                                    
                                    f.write("-" * 80 + "\n")
                                    f.write("\n\nVIABLE NATIONS (ready for batch import):\n")
                                    f.write("-" * 40 + "\n")
                                    for name in viable_nations:
                                        f.write(f"{name}\n")
                                    
                                    f.write("\n\nPOSSIBLE NATIONS (11-22 players):\n")
                                    f.write("-" * 40 + "\n")
                                    for name in possible_nations:
                                        f.write(f"{name}\n")
                                
                                messagebox.showinfo("Export Complete", f"Nation list exported to:\n{export_path}")
                            except Exception as e:
                                messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
                        root.destroy()
                        return
                    else:
                        # Enter specific nations - need to show root temporarily for simpledialog
                        root.deiconify()
                        root.lift()
                        root.focus_force()
                        
                        nations_input = simpledialog.askstring(
                            "Enter Nations",
                            "Enter nation names separated by commas:\n\n" +
                            f"Viable: {', '.join(viable_nations[:8])}...\n\n" +
                            "Example: England, France, Germany",
                            parent=root)
                        
                        root.withdraw()
                        
                        if not nations_input:
                            root.destroy()
                            return
                        
                        # Parse input
                        selected_nations = [n.strip() for n in nations_input.split(',') if n.strip()]
                        
                        # Validate nations
                        valid_nations = []
                        for nation in selected_nations:
                            if nation in nation_id_map:
                                valid_nations.append(nation)
                            else:
                                # Try partial match
                                matches = [n for n in nation_id_map.keys() if nation.lower() in n.lower()]
                                if matches:
                                    valid_nations.append(matches[0])
                                    print(f"Matched '{nation}' to '{matches[0]}'")
                                else:
                                    print(f"Warning: '{nation}' not found, skipping")
                        
                        if not valid_nations:
                            messagebox.showerror("Error", "No valid nations entered.")
                            root.destroy()
                            return
                        
                        selected_nations = valid_nations
                        print(f"Selected {len(selected_nations)} nations: {selected_nations}")
            else:
                messagebox.showinfo("No Viable Nations", 
                    "No nations have 23+ players with 2+ goalkeepers.\n\n" +
                    "Check the console for the full list of possible nations.")
                root.destroy()
                return
            
            # Ask about formation - same for all or random
            use_random_formations = messagebox.askyesno("Formation Selection",
                "How do you want to assign formations?\n\n" +
                "Yes - RANDOM formation for each team\n" +
                "No - Same formation for all teams")
            
            if use_random_formations:
                selected_formation = None  # Will be randomized per team
                print("Using RANDOM formations for each team")
            else:
                # Ask user to select a formation (same for all teams)
                root.deiconify()
                root.lift()
                selected_formation = select_formation_dialog(root, formations)
                root.withdraw()
                if not selected_formation:
                    selected_formation = next((f for f in formations if f["name"] == "4-3-3"), None)
                    print(f"No formation selected, defaulting to 4-3-3")
                else:
                    print(f"Using formation {selected_formation['name']} for all teams")
            
            # Now ask for team IDs for each nation individually
            messagebox.showinfo("Team IDs", 
                f"You will now enter a unique Team ID for each of the {len(selected_nations)} nations.\n\n" +
                "Press Cancel at any time to skip remaining nations.")
            
            # Collect team IDs for each nation
            nation_team_ids = {}
            for nation_name in selected_nations:
                root.deiconify()
                root.lift()
                team_id_str = simpledialog.askstring("National Team Creator",
                                                     f"Enter Team ID for {nation_name}:\n\n" +
                                                     f"(Nation {len(nation_team_ids) + 1} of {len(selected_nations)})",
                                                     parent=root)
                root.withdraw()
                
                if not team_id_str:
                    # User cancelled - ask if they want to proceed with what they have
                    if nation_team_ids:
                        proceed = messagebox.askyesno("Continue?", 
                            f"You've entered {len(nation_team_ids)} team IDs.\n" +
                            "Do you want to create those teams now?\n\n" +
                            "Yes - Create the teams entered so far\n" +
                            "No - Cancel everything")
                        if proceed:
                            break
                    root.destroy()
                    return
                
                try:
                    team_id = int(team_id_str)
                    nation_team_ids[nation_name] = team_id
                except ValueError:
                    messagebox.showerror("Error", f"Invalid team ID for {nation_name}. Skipping this nation.")
                    continue
            
            if not nation_team_ids:
                messagebox.showinfo("Cancelled", "No team IDs entered.")
                root.destroy()
                return
            
            # Get existing team IDs for duplicate checking
            teams_txt_path = os.path.join(input_dir, "teams.txt")
            existing_team_ids = get_existing_team_ids(teams_txt_path)
            
            # Confirmation loop - allow editing until user confirms or cancels
            while True:
                # Check for duplicate team IDs
                duplicates = []
                for nation_name, team_id in nation_team_ids.items():
                    if team_id in existing_team_ids:
                        duplicates.append(f"  ⚠️ {nation_name}: {team_id} (already used by '{existing_team_ids[team_id]}')")
                
                # Check for duplicate IDs within the current batch
                id_counts = {}
                for nation_name, team_id in nation_team_ids.items():
                    if team_id in id_counts:
                        id_counts[team_id].append(nation_name)
                    else:
                        id_counts[team_id] = [nation_name]
                
                internal_duplicates = []
                for team_id, nations in id_counts.items():
                    if len(nations) > 1:
                        internal_duplicates.append(f"  ⚠️ ID {team_id} used by: {', '.join(nations)}")
                
                # Show confirmation before creating teams
                print("\n" + "="*60)
                print("REVIEW: TEAMS TO BE CREATED")
                print("="*60)
                for idx, (nation_name, team_id) in enumerate(nation_team_ids.items(), 1):
                    nation_id = nation_id_map.get(nation_name, "?")
                    warning = " ⚠️ DUPLICATE!" if team_id in existing_team_ids else ""
                    print(f"  {idx}. {nation_name:<25} -> Team ID: {team_id} (Nation ID: {nation_id}){warning}")
                
                if duplicates:
                    print("\n⚠️ DUPLICATE TEAM IDs FOUND (already exist in teams.txt):")
                    for d in duplicates:
                        print(d)
                
                if internal_duplicates:
                    print("\n⚠️ DUPLICATE IDs IN CURRENT BATCH:")
                    for d in internal_duplicates:
                        print(d)
                
                print("="*60 + "\n")
                
                # Build confirmation message
                if len(nation_team_ids) <= 10:
                    confirm_list = "\n".join([f"{idx}. {name}: {tid}" for idx, (name, tid) in enumerate(nation_team_ids.items(), 1)])
                else:
                    items = list(nation_team_ids.items())
                    confirm_list = "\n".join([f"{idx}. {name}: {tid}" for idx, (name, tid) in enumerate(items[:8], 1)])
                    confirm_list += f"\n... ({len(items) - 10} more) ...\n"
                    confirm_list += "\n".join([f"{idx}. {name}: {tid}" for idx, (name, tid) in enumerate(items[-2:], len(items) - 1)])
                
                # Add warnings to dialog
                warning_text = ""
                if duplicates or internal_duplicates:
                    warning_text = "\n⚠️ DUPLICATE IDs DETECTED - Check console!\n"
                
                # Ask what to do
                action = simpledialog.askstring("Confirm Team Creation",
                    f"Ready to create {len(nation_team_ids)} national teams:\n\n" +
                    f"{confirm_list}\n" +
                    f"{warning_text}\n" +
                    "Enter:\n" +
                    "  Y or YES - Create teams\n" +
                    "  E or EDIT - Edit a team ID\n" +
                    "  P or PREVIEW - Preview a team's starting XI\n" +
                    "  S or SAVE - Save team IDs to file\n" +
                    "  L or LOAD - Load team IDs from file\n" +
                    "  C or CANCEL - Cancel everything\n\n" +
                    "(Check console for full list)",
                    parent=root)
                
                if not action:
                    action = 'cancel'
                
                action = action.strip().upper()
                
                if action in ['Y', 'YES']:
                    # Check for duplicates one more time
                    if duplicates or internal_duplicates:
                        confirm_duplicates = messagebox.askyesno("Duplicate Warning",
                            "There are duplicate team IDs!\n\n" +
                            "This may cause issues in the game.\n\n" +
                            "Are you sure you want to proceed?")
                        if not confirm_duplicates:
                            continue
                    # Proceed with creation
                    break
                    
                elif action in ['C', 'CANCEL']:
                    messagebox.showinfo("Cancelled", "Team creation cancelled. No changes made.")
                    root.destroy()
                    return
                    
                elif action in ['S', 'SAVE']:
                    # Save team ID mappings
                    save_path = filedialog.asksaveasfilename(
                        title="Save Team ID Mappings",
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile="nation_team_ids.txt"
                    )
                    if save_path:
                        if save_team_id_mappings(nation_team_ids, save_path):
                            messagebox.showinfo("Saved", f"Team ID mappings saved to:\n{save_path}")
                        else:
                            messagebox.showerror("Error", "Failed to save team ID mappings.")
                            
                elif action in ['L', 'LOAD']:
                    # Load team ID mappings
                    load_path = filedialog.askopenfilename(
                        title="Load Team ID Mappings",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                    )
                    if load_path:
                        loaded_ids = load_team_id_mappings(load_path)
                        if loaded_ids:
                            # Merge with current (loaded IDs take precedence)
                            for name, tid in loaded_ids.items():
                                if name in nation_team_ids:
                                    nation_team_ids[name] = tid
                                    print(f"Updated {name} -> {tid}")
                            messagebox.showinfo("Loaded", f"Loaded {len(loaded_ids)} team ID mappings.")
                        else:
                            messagebox.showerror("Error", "Failed to load team ID mappings.")
                            
                elif action in ['P', 'PREVIEW']:
                    # Preview starting XI for a nation
                    nations_list = list(nation_team_ids.keys())
                    preview_prompt = "Enter number or nation name to preview:\n\n"
                    for idx, name in enumerate(nations_list[:15], 1):
                        preview_prompt += f"{idx}. {name}\n"
                    if len(nations_list) > 15:
                        preview_prompt += f"... and {len(nations_list) - 15} more\n"
                    
                    root.deiconify()
                    root.lift()
                    preview_choice = simpledialog.askstring("Preview Starting XI",
                        preview_prompt,
                        parent=root)
                    root.withdraw()
                    
                    if preview_choice:
                        preview_choice = preview_choice.strip()
                        nation_to_preview = None
                        
                        if preview_choice.isdigit():
                            idx = int(preview_choice)
                            if 1 <= idx <= len(nations_list):
                                nation_to_preview = nations_list[idx - 1]
                        else:
                            for name in nations_list:
                                if preview_choice.lower() in name.lower():
                                    nation_to_preview = name
                                    break
                        
                        if nation_to_preview:
                            nation_id = nation_id_map.get(nation_to_preview)
                            if nation_id:
                                preview = get_starting_xi_preview(players_txt_path, nation_id, nation_to_preview)
                                print(preview)
                                messagebox.showinfo(f"Starting XI: {nation_to_preview}", 
                                    f"Check the console for the full starting XI preview!\n\n" +
                                    f"(Team ID: {nation_team_ids[nation_to_preview]})")
                            else:
                                messagebox.showerror("Error", f"Could not find nation ID for {nation_to_preview}")
                        else:
                            messagebox.showerror("Error", f"Could not find nation: {preview_choice}")
                
                elif action in ['E', 'EDIT']:
                    # Show edit dialog
                    nations_list = list(nation_team_ids.keys())
                    edit_prompt = "Enter the number or nation name to edit:\n\n"
                    for idx, name in enumerate(nations_list[:15], 1):
                        warning = " ⚠️" if nation_team_ids[name] in existing_team_ids else ""
                        edit_prompt += f"{idx}. {name}: {nation_team_ids[name]}{warning}\n"
                    if len(nations_list) > 15:
                        edit_prompt += f"... and {len(nations_list) - 15} more (check console)\n"
                    
                    root.deiconify()
                    root.lift()
                    edit_choice = simpledialog.askstring("Edit Team ID",
                        edit_prompt + "\n(Enter number or nation name)",
                        parent=root)
                    root.withdraw()
                    
                    if edit_choice:
                        edit_choice = edit_choice.strip()
                        nation_to_edit = None
                        
                        if edit_choice.isdigit():
                            idx = int(edit_choice)
                            if 1 <= idx <= len(nations_list):
                                nation_to_edit = nations_list[idx - 1]
                        else:
                            for name in nations_list:
                                if edit_choice.lower() in name.lower():
                                    nation_to_edit = name
                                    break
                        
                        if nation_to_edit:
                            root.deiconify()
                            root.lift()
                            new_id_str = simpledialog.askstring("Edit Team ID",
                                f"Enter new Team ID for {nation_to_edit}:\n\n" +
                                f"Current ID: {nation_team_ids[nation_to_edit]}",
                                parent=root)
                            root.withdraw()
                            
                            if new_id_str:
                                try:
                                    new_id = int(new_id_str)
                                    old_id = nation_team_ids[nation_to_edit]
                                    nation_team_ids[nation_to_edit] = new_id
                                    print(f"Updated {nation_to_edit}: {old_id} -> {new_id}")
                                    messagebox.showinfo("Updated", f"{nation_to_edit} Team ID changed:\n{old_id} → {new_id}")
                                except ValueError:
                                    messagebox.showerror("Error", "Invalid team ID. Must be a number.")
                        else:
                            messagebox.showerror("Error", f"Could not find nation: {edit_choice}")
                else:
                    messagebox.showinfo("Invalid Input", "Please enter Y, E, P, S, L, or C")
            
            # Process all nations with their assigned team IDs
            league_id = 78
            success_count = 0
            created_teams = []
            
            for nation_name, team_id in nation_team_ids.items():
                nation_id = nation_id_map.get(nation_name)
                if not nation_id:
                    print(f"✗ Could not find nation ID for {nation_name}. Skipping.")
                    continue
                
                # Pick formation - random if not set, otherwise use selected
                if selected_formation is None:
                    team_formation = random.choice(formations)
                    print(f"\nProcessing: {nation_name} (Team ID: {team_id}, Nation ID: {nation_id}, Formation: {team_formation['name']})")
                else:
                    team_formation = selected_formation
                    print(f"\nProcessing: {nation_name} (Team ID: {team_id}, Nation ID: {nation_id})")
                
                appender = TeamAppender(nation_name, team_id, league_id, nation_id, is_national_team=True)
                
                if appender.load_player_data(players_txt_path):
                    if appender.process_files(input_dir, team_formation):
                        success_count += 1
                        if selected_formation is None:
                            created_teams.append(f"{nation_name} (ID: {team_id}, {team_formation['name']})")
                        else:
                            created_teams.append(f"{nation_name} (ID: {team_id})")
                        print(f"✓ {nation_name} created successfully!")
                    else:
                        print(f"✗ Failed to process files for {nation_name}")
                else:
                    print(f"✗ Failed to load players for {nation_name}")
            
            # Show results
            if success_count > 0:
                # Show created teams (limit display if many)
                if len(created_teams) <= 5:
                    teams_str = "\n".join(created_teams)
                else:
                    teams_str = "\n".join(created_teams[:5]) + f"\n... and {len(created_teams) - 5} more"
                
                messagebox.showinfo("Success",
                                   f"Successfully created {success_count} out of {len(nation_team_ids)} national teams!\n\n" +
                                   f"{teams_str}")
            else:
                messagebox.showwarning("Error", "Failed to create any national teams.")
            
            root.destroy()
            return

        elif national_team_mode == 'batch':
            # Batch mode from text file
            messagebox.showinfo("National Team Creator",
                                "Please select a text file containing nation names and team IDs.\n\n" +
                                "Expected format for each line: NationName,TeamID\n" +
                                "Example: England,5000")

            teams_file_path = filedialog.askopenfilename(
                title="Select Teams Text File",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if not teams_file_path:
                messagebox.showinfo("Cancelled", "No teams file selected. Exiting.")
                root.destroy()
                return

            # Process the teams file
            success_count, total_count = create_national_teams_from_file(
                teams_file_path, input_dir, players_txt_path, nation_id_map, formations)

            # Show results
            if success_count > 0:
                messagebox.showinfo("Success",
                                    f"Successfully created {success_count} out of {total_count} national teams!")
            else:
                messagebox.showwarning("Error",
                                       "Failed to create any national teams. Check the console for details.")
            
            root.destroy()
            return

        elif national_team_mode == 'interactive':
            # Sequential team creation loop (original code)
            continue_creating = True
            while continue_creating:
                # Get team ID for each team
                root.deiconify()
                root.lift()
                team_id_str = simpledialog.askstring("National Team Creator",
                                                     "Enter the team ID for this national team:",
                                                     parent=root)
                root.withdraw()
                if not team_id_str:
                    messagebox.showinfo("Cancelled", "No team ID entered. Exiting.")
                    root.destroy()
                    return
                try:
                    current_team_id = int(team_id_str)
                except ValueError:
                    messagebox.showerror("Error", "Team ID must be a number.")
                    continue  # Ask for team ID again

                # Create a string with popular nations
                popular_nations = ["England", "France", "Germany", "Spain", "Italy", "Brazil", "Argentina",
                                   "Portugal", "Belgium", "Holland", "Mexico", "United States", "Japan",
                                   "Australia", "Egypt", "Nigeria", "South Africa"]

                # Filter to include only nations in our mapping
                popular_nations = [n for n in popular_nations if n in nation_id_map]

                # Nation selection dialog
                root.deiconify()
                root.lift()
                selected_nation = simpledialog.askstring(
                    "Select Nation",
                    f"Type a nation name (team ID: {current_team_id}):\n\n" +
                    "Popular nations:\n" + "\n".join(popular_nations) +
                    "\n\n(You can type any valid nation name)",
                    parent=root)
                root.withdraw()

                if not selected_nation:
                    messagebox.showinfo("Cancelled", "No nation selected. Exiting.")
                    root.destroy()
                    return

                # Check if the entered nation is valid
                if selected_nation not in nation_id_map:
                    # Try to find a partial match
                    matching_nations = [n for n in nation_id_map.keys() if selected_nation.lower() in n.lower()]
                    if matching_nations:
                        selected_nation = matching_nations[0]
                        print(f"Matched partial entry to: {selected_nation}")
                    else:
                        messagebox.showerror("Error", f"'{selected_nation}' is not a valid nation name.")
                        continue  # Skip to next iteration

                # Ask user to select a formation
                root.deiconify()
                root.lift()
                selected_formation = select_formation_dialog(root, formations)
                root.withdraw()
                if not selected_formation:
                    # User cancelled or didn't select a formation
                    selected_formation = next((f for f in formations if f["name"] == "4-3-3"), None)
                    print(f"No formation selected, defaulting to 4-3-3")

                # Ask for stadium ID (optional)
                root.deiconify()
                root.lift()
                stadium_id_str = simpledialog.askstring("National Team Creator",
                                                        "Enter the stadium ID for this team (or leave blank to skip):",
                                                        parent=root)
                root.withdraw()
                stadium_id = None
                if stadium_id_str:
                    try:
                        stadium_id = int(stadium_id_str)
                    except ValueError:
                        messagebox.showwarning("Warning", "Invalid stadium ID. Stadium linking will be skipped.")

                selected_nations = [selected_nation]
                print(f"Selected nation: {selected_nations[0]} (ID: {nation_id_map[selected_nations[0]]})")
                print(f"Selected formation: {selected_formation['name']}")
                if stadium_id:
                    print(f"Stadium ID: {stadium_id}")

                # Process the national team
                league_id = 78  # Always 78 for national teams
                success_count = 0

                # Create a team appender for this national team
                appender = TeamAppender(selected_nation, current_team_id, league_id,
                                        nation_id_map[selected_nation], is_national_team=True, stadium_id=stadium_id)

                # Load player data and process files
                if appender.load_player_data(players_txt_path):
                    if appender.process_files(input_dir, selected_formation):
                        success_count = 1
                else:
                    print(f"Failed to load player data for {selected_nation}.")

                # Show results
                if success_count == 1:
                    messagebox.showinfo("Success",
                                        f"{selected_nation} national team created with ID {current_team_id} using {selected_formation['name']} formation!")
                else:
                    messagebox.showwarning("Error",
                                           f"Failed to create the {selected_nation} national team. Check the console for details.")

                # Ask if user wants to create another team
                continue_creating = messagebox.askyesno("Continue?", "Create another national team?")

        root.destroy()
        return

    else:
        # Regular club team creation (existing code)
        print("Selected club team option")

        # Load formations data
        formations = load_formations()

        # Get league ID (single league for all teams)
        root.deiconify()
        root.lift()
        league_id_str = simpledialog.askstring("Club Team Creator", "Enter the league ID for club teams:",
                                               parent=root)
        root.withdraw()
        if not league_id_str:
            messagebox.showerror("Error", "League ID is required.")
            root.destroy()
            return
        try:
            league_id = int(league_id_str)
        except ValueError:
            messagebox.showerror("Error", "League ID must be a number.")
            root.destroy()
            return

        # Ask user if they want to select multiple files at once or create teams one by one
        multi_select = messagebox.askyesno("Club Team Creator",
                                           "Do you want to select multiple team files at once?\n\n" +
                                           "Yes - Select multiple files (batch mode)\n" +
                                           "No - Create teams one by one (interactive mode)")

        if multi_select:
            # Batch mode - Select multiple files at once
            # Get starting team ID for batch mode
            root.deiconify()
            root.lift()
            team_id_str = simpledialog.askstring("Club Team Creator (Batch Mode)",
                                                 "Enter the starting team ID:\n(Teams will receive sequential IDs from this number)",
                                                 parent=root)
            root.withdraw()
            if not team_id_str:
                messagebox.showerror("Error", "Starting team ID is required for batch mode.")
                root.destroy()
                return
            try:
                current_team_id = int(team_id_str)
            except ValueError:
                messagebox.showerror("Error", "Team ID must be a number.")
                root.destroy()
                return

            messagebox.showinfo("Club Team Creator",
                                "Please select all the player CSV/TXT files for the teams you want to create.\n" +
                                "The team names will be taken from the filenames.\n" +
                                "Hold Ctrl to select multiple files.")

            player_files = filedialog.askopenfilenames(
                title="Select Player CSV or TXT Files",
                filetypes=[("CSV/TXT files", "*.csv *.txt"), ("All files", "*.*")]
            )

            if not player_files:
                messagebox.showerror("Error", "No player files selected. Exiting.")
                root.destroy()
                return

            # Ask user to select a formation (same for all teams in batch mode)
            selected_formation = select_formation_dialog(root, formations)
            if not selected_formation:
                # User cancelled or didn't select a formation
                selected_formation = next((f for f in formations if f["name"] == "4-3-3"), None)
                print(f"No formation selected, defaulting to 4-3-3")

            # Process all teams
            success_count = process_multiple_teams(player_files, current_team_id, league_id, input_dir,
                                                   is_national_teams=False, selected_formation=selected_formation)

            # Show final results
            if success_count == len(player_files):
                messagebox.showinfo("Success", f"All {success_count} teams were successfully created!")
            else:
                messagebox.showwarning("Partial Success",
                                       f"{success_count} out of {len(player_files)} teams were successfully created.\n" +
                                       "Check the console for details on any errors.")

            # Ask if user wants to create more teams
            if messagebox.askyesno("Continue?", "Create more club teams?"):
                # Update current_team_id for the next batch
                next_team_id = current_team_id + len(player_files)
                messagebox.showinfo("Next Team ID",
                                    f"Your next team ID will be: {next_team_id}\n" +
                                    "Please run the program again to continue.")

        else:
            # Interactive mode - Create teams one by one
            continue_creating = True
            total_success_count = 0
            created_team_ids = []

            while continue_creating:
                # Ask for team ID each time - just like for national teams
                root.deiconify()
                root.lift()
                team_id_str = simpledialog.askstring("Club Team Creator",
                                                     "Enter the team ID for this club team:",
                                                     parent=root)
                root.withdraw()
                if not team_id_str:
                    messagebox.showinfo("Cancelled", "No team ID entered. Exiting interactive mode.")
                    break

                try:
                    current_team_id = int(team_id_str)
                except ValueError:
                    messagebox.showerror("Error", "Team ID must be a number.")
                    continue  # Ask for team ID again

                # Ask for stadium ID (optional)
                root.deiconify()
                root.lift()
                stadium_id_str = simpledialog.askstring("Club Team Creator",
                                                        "Enter the stadium ID for this team (or leave blank to skip):",
                                                        parent=root)
                root.withdraw()
                stadium_id = None
                if stadium_id_str:
                    try:
                        stadium_id = int(stadium_id_str)
                    except ValueError:
                        messagebox.showwarning("Warning", "Invalid stadium ID. Stadium linking will be skipped.")

                # Ask user to select the player file
                messagebox.showinfo("Club Team Creator",
                                    f"Please select the player CSV/TXT file for team ID: {current_team_id}")

                player_file = filedialog.askopenfilename(
                    title=f"Select Player CSV/TXT File for Team ID: {current_team_id}",
                    filetypes=[("CSV/TXT files", "*.csv *.txt"), ("All files", "*.*")]
                )

                if not player_file:
                    messagebox.showinfo("Cancelled", "No player file selected.")
                    # Ask if they want to exit or try again
                    if not messagebox.askyesno("Continue?", "Do you want to select a different file?"):
                        break
                    continue

                # Extract team name from the filename
                team_name = os.path.basename(player_file)
                if team_name.lower().endswith('.csv') or team_name.lower().endswith('.txt'):
                    team_name = team_name[:-4]  # Remove extension

                # Ask user to select a formation
                root.deiconify()
                root.lift()
                selected_formation = select_formation_dialog(root, formations)
                root.withdraw()
                if not selected_formation:
                    # User cancelled or didn't select a formation
                    selected_formation = next((f for f in formations if f["name"] == "4-3-3"), None)
                    print(f"No formation selected, defaulting to 4-3-3")

                print(f"\nProcessing club team: {team_name} (ID: {current_team_id})")
                print(f"Selected formation: {selected_formation['name']}")
                if stadium_id:
                    print(f"Stadium ID: {stadium_id}")

                # Create a team appender for this team
                appender = TeamAppender(team_name, current_team_id, league_id, stadium_id=stadium_id)

                # Load player data and process files
                success = False
                if appender.load_player_data(player_file):
                    if appender.process_files(input_dir, selected_formation):
                        success = True
                        total_success_count += 1
                        created_team_ids.append(current_team_id)

                # Show results
                if success:
                    messagebox.showinfo("Success",
                                        f"{team_name} club team created with ID {current_team_id} using {selected_formation['name']} formation!")
                else:
                    messagebox.showwarning("Error",
                                           f"Failed to create the {team_name} club team. Check the console for details.")

                # Ask if user wants to create another team
                continue_creating = messagebox.askyesno("Continue?", "Create another club team?")

            # Show final results
            if total_success_count > 0:
                created_team_ids.sort()  # Sort IDs for better display
                if len(created_team_ids) > 10:
                    # If many teams, just show the count and range
                    messagebox.showinfo("Final Results",
                                        f"Created {total_success_count} club teams successfully!\n" +
                                        f"Team ID range: {min(created_team_ids)} - {max(created_team_ids)}")
                else:
                    # If few teams, show all the IDs
                    id_text = ", ".join(str(tid) for tid in created_team_ids)
                    messagebox.showinfo("Final Results",
                                        f"Created {total_success_count} club teams successfully!\n" +
                                        f"Team IDs: {id_text}")

        root.destroy()
        return



# Also need to update process_multiple_teams function to accept formation parameter
def process_multiple_teams(team_files, starting_team_id, league_id, input_dir, is_national_teams=False,
                           players_txt_path=None, nation_id_map=None, selected_formation=None):
    """
    Process multiple teams one after another

    Args:
        team_files (list): List of paths to player CSV/TXT files (or nation names for national teams)
        starting_team_id (int): ID to assign to the first team
        league_id (int): League ID to use for all teams (78 for national teams)
        input_dir (str): Directory containing all game files
        is_national_teams (bool): Whether these are national teams
        players_txt_path (str): Path to players.txt file for national teams
        nation_id_map (dict): Mapping of nation names to nation IDs
        selected_formation (dict): Formation data to use for all teams

    Returns:
        int: Number of teams successfully processed
    """
    print(f"\nProcessing {len(team_files)} teams starting with ID: {starting_team_id}")

    if is_national_teams:
        print("Processing as NATIONAL TEAMS")
        print(f"Using players.txt file: {players_txt_path}")
        league_id = 78  # Always 78 for national teams

    print(f"All teams will be assigned to league ID: {league_id}")
    if selected_formation:
        print(f"All teams will use formation: {selected_formation['name']}")

    success_count = 0
    current_team_id = starting_team_id

    for i, team_file_or_name in enumerate(team_files):
        try:
            if is_national_teams:
                # For national teams, team_file_or_name is the nation name
                team_name = team_file_or_name
                nation_id = nation_id_map.get(team_name)

                if not nation_id:
                    print(f"✗ Could not find nation ID for {team_name}. Skipping.")
                    continue

                print(
                    f"\nProcessing national team {i + 1}/{len(team_files)}: {team_name} (ID: {current_team_id}, Nation ID: {nation_id})")

                # Create a team appender for this national team
                appender = TeamAppender(team_name, current_team_id, league_id, nation_id, is_national_team=True)

                # Load player data from players.txt
                if not appender.load_player_data(players_txt_path):
                    print(f"✗ Failed to load player data for {team_name}. Skipping.")
                    continue
            else:
                # Regular club team processing
                team_file = team_file_or_name

                # Extract team name from the filename
                team_name = os.path.basename(team_file)
                if team_name.lower().endswith('.csv') or team_name.lower().endswith('.txt'):
                    team_name = team_name[:-4]  # Remove extension

                print(f"\nProcessing team {i + 1}/{len(team_files)}: {team_name} (ID: {current_team_id})")

                # Create a team appender for this team
                appender = TeamAppender(team_name, current_team_id, league_id)

                # Load player data
                if not appender.load_player_data(team_file):
                    print(f"✗ Failed to load player data for {team_name}. Skipping.")
                    continue

            # Process all files
            if appender.process_files(input_dir, selected_formation):
                success_count += 1
                print(f"✓ Team {team_name} processed successfully.")
            else:
                print(f"✗ Some errors occurred while processing team {team_name}.")

            # Increment team ID for the next team
            current_team_id += 1
        except Exception as e:
            print(f"✗ Error processing team {team_file_or_name}: {str(e)}")
            traceback.print_exc()
            continue

    return success_count


if __name__ == "__main__":
    print("Script starting...")
    main()