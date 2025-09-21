from langchain_core.tools import tool
from app.services import api_client # Import the singleton instance
from datetime import datetime, timezone, date, timedelta
from typing import Any, Dict, Optional
import logging
from app.services.team_name_cache import team_name_cache
from app.services.tournament_name_cache import tournament_name_cache
from thefuzz import process, fuzz
import dateparser
import json
import calendar

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def _get_match_odds_data(team_one: str, team_two: str) -> dict:
    """
    Internal helper function (not a tool) to find a match and get all its odds data.
    Returns a dictionary with odds info or an error.
    """
    # This contains the complete logic from the old get_odds_for_match tool
    canonical_team_one = team_name_cache.get_best_match(team_one)
    canonical_team_two = team_name_cache.get_best_match(team_two)
    if not canonical_team_one or not canonical_team_two:
        return {"error": f"Could not find one or both teams: '{team_one}', '{team_two}'."}
    if canonical_team_one == canonical_team_two:
        return {"error": "Cannot get odds for a team against itself."}
    
    all_fixtures_response = api_client.get_fixtures_by_sport(sport_id=1)
    if not all_fixtures_response:
        return {"error": "Could not retrieve match data from the API."}
    fixtures_list = all_fixtures_response.get("data") if isinstance(all_fixtures_response, dict) else all_fixtures_response
    if not fixtures_list: return {"error": "No match data found."}

    found_fixture = None
    for fixture in fixtures_list:
        home_team = fixture.get("home_team_data", {}).get("name", {}).get("en")
        away_team = fixture.get("away_team_data", {}).get("name", {}).get("en")
        if home_team and away_team:
            home_canonical = team_name_cache.get_best_match(home_team)
            away_canonical = team_name_cache.get_best_match(away_team)
            if ((home_canonical == canonical_team_one and away_canonical == canonical_team_two) or
                (home_canonical == canonical_team_two and away_canonical == canonical_team_one)):
                found_fixture = fixture
                break
    
    if not found_fixture:
        return {"error": f"No upcoming match found between {canonical_team_one} and {canonical_team_two}."}

    fixture_id = found_fixture.get("id")
    tournament_id = found_fixture.get("tournament_id")
    sport_id = found_fixture.get("sport_id", "1")
    home_team_name = found_fixture.get("home_team_data", {}).get("name", {}).get("en", "Home")
    away_team_name = found_fixture.get("away_team_data", {}).get("name", {}).get("en", "Away")

    if not fixture_id or not tournament_id:
        return {"error": "Found match but missing IDs for odds."}

    odds_data = api_client.get_odds(fixture_id=fixture_id, tournament_id=tournament_id, sport_id=sport_id)
    if not odds_data or odds_data.get("status") != "Active":
        return {"error": "Odds are currently inactive or unavailable.", "api_status": odds_data.get('status')}

    # (The same comprehensive odds parsing logic as before)
    result_market = odds_data.get("result")
    both_teams_score_market = odds_data.get("both_teams_to_score")
    double_chance_market = odds_data.get("double_chance")
    over_under_market = odds_data.get("over_under")
    handicap_market = odds_data.get("handicap")
    half_time_result_market = odds_data.get("half_time_result")
    # Helper to safely extract odds
    def get_odds_from_market(market, key):
        return market.get(key, {}).get("odds") if market and isinstance(market.get(key), dict) else None
    
    odds_info = {
        "match": f"{home_team_name} vs {away_team_name}",
        "match_result": {
            "home_win": get_odds_from_market(result_market, "homeTeam"),
            "away_win": get_odds_from_market(result_market, "awayTeam"),
            "draw": get_odds_from_market(result_market, "tie"),
        },
        "both_teams_to_score": {
            "yes": get_odds_from_market(both_teams_score_market, "yes"),
            "no": get_odds_from_market(both_teams_score_market, "no"),
        },
        "double_chance": {
            "home_or_draw": get_odds_from_market(double_chance_market, "homeTeam_or_draw"),
            "away_or_draw": get_odds_from_market(double_chance_market, "awayTeam_or_draw"),
            "home_or_away": get_odds_from_market(double_chance_market, "homeTeam_or_awayTeam"),
        },
        "over_under": {
            "over": {
                "line": over_under_market.get("over", {}).get("name"),
                "odds": get_odds_from_market(over_under_market, "over")
            } if over_under_market and "over" in over_under_market else None,
            "under": {
                "line": over_under_market.get("under", {}).get("name"),
                "odds": get_odds_from_market(over_under_market, "under")
            } if over_under_market and "under" in over_under_market else None,
        },
        "handicap": {
            "home": {
                "line": handicap_market.get("homeTeam", {}).get("name"),
                "odds": get_odds_from_market(handicap_market, "homeTeam")
            } if handicap_market and "homeTeam" in handicap_market else None,
            "away": {
                "line": handicap_market.get("awayTeam", {}).get("name"),
                "odds": get_odds_from_market(handicap_market, "awayTeam")
            } if handicap_market and "awayTeam" in handicap_market else None,
        },
        "half_time_result": {
            "home_win": get_odds_from_market(half_time_result_market, "homeTeam"),
            "away_win": get_odds_from_market(half_time_result_market, "awayTeam"),
            "draw": get_odds_from_market(half_time_result_market, "tie"),
        }
    }
    return odds_info

def _parse_date_range(query: str) -> (Optional[date], Optional[date]):
    """
    Parses a user's date query into a start and end date.
    Handles single dates, "today", "tomorrow", and ranges like "this weekend",
    "this month", and "end of the month".
    """
    today = datetime.now(timezone.utc).date()
    query = query.lower()

    # Handle ranges first
    if "weekend" in query:
        start_of_weekend = today + timedelta(days=(5 - today.weekday() + 7) % 7) # Next Saturday
        end_of_weekend = start_of_weekend + timedelta(days=1)
        return start_of_weekend, end_of_weekend
    
    if "end of" in query and "month" in query:
        last_day_of_month = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        start_of_end = last_day_of_month - timedelta(days=4)
        return start_of_end, last_day_of_month

    if "month" in query: # "this month"
        first_day_of_month = date(today.year, today.month, 1)
        last_day_of_month = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        return first_day_of_month, last_day_of_month
        
    # Handle single dates using dateparser
    date_settings = {'TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': True, 'PREFER_DATES_FROM': 'future'}
    parsed_date = dateparser.parse(query, settings=date_settings)
    if parsed_date:
        target_date = parsed_date.date()
        return target_date, target_date
    
    return None, None

def _analyze_daily_odds(date_query: str) -> dict:
    """
    Internal helper to analyze all matches on a given day/range.
    Returns a structured dictionary with analysis results or an error.
    """
    # 1. Parse Date Range
    start_date, end_date = _parse_date_range(date_query)
    if not start_date or not end_date:
        return {"error": f"Couldn't understand the date or range '{date_query}'."}

    # 2. Get all fixtures and filter
    response = api_client.get_fixtures_by_sport(sport_id=1)
    if not response: return {"error": "Could not retrieve fixtures from the API."}
    fixtures_list = response.get("data") if isinstance(response, dict) else response
    if not fixtures_list: return {"error": "No fixtures data was found to analyze."}

    date_fixtures = []
    # (Filtering logic remains the same)
    for f in fixtures_list:
        fixture_datetime = None
        try:
            fixture_date_str = f.get("fixture_date"); start_time_str = f.get("startTime")
            if fixture_date_str: fixture_datetime = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00"))
            elif start_time_str:
                current_year = datetime.now().year; full_date_str = f"{current_year}-{start_time_str}"
                fixture_datetime = datetime.strptime(full_date_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            if fixture_datetime and start_date <= fixture_datetime.date() <= end_date: date_fixtures.append(f)
        except (ValueError, TypeError): continue
    
    if not date_fixtures: return {"error": f"No matches found for the period '{date_query}' to analyze."}

    # 3. Analyze odds
    safest_bet = {"odds": float('inf'), "fixture": None, "team": None}
    riskiest_bet = {"odds": 0, "fixture": None, "team": None}
    most_competitive = {"diff": float('inf'), "fixture": None}

    for fixture in date_fixtures:
        # (Odds analysis logic remains the same)
        fixture_id=fixture.get("id"); tournament_id=fixture.get("tournament_id"); sport_id=fixture.get("sport_id", "1")
        if not all([fixture_id, tournament_id, sport_id]): continue
        odds_data = api_client.get_odds(fixture_id=fixture_id, tournament_id=tournament_id, sport_id=sport_id)
        if not odds_data or odds_data.get("status") != "Active": continue
        result_market = odds_data.get("result")
        if not result_market: continue
        home_data = result_market.get("homeTeam"); away_data = result_market.get("awayTeam")
        if not home_data or not away_data or "odds" not in home_data or "odds" not in away_data: continue
        home_odds, away_odds = home_data["odds"], away_data["odds"]
        home_name, away_name = home_data.get("name", "Home"), away_data.get("name", "Away")
        match_name = f"{home_name} vs {away_name}"
        if home_odds < safest_bet["odds"]: safest_bet.update({"odds": home_odds, "fixture": match_name, "team": home_name})
        if away_odds < safest_bet["odds"]: safest_bet.update({"odds": away_odds, "fixture": match_name, "team": away_name})
        if home_odds > riskiest_bet["odds"]: riskiest_bet.update({"odds": home_odds, "fixture": match_name, "team": home_name})
        if away_odds > riskiest_bet["odds"]: riskiest_bet.update({"odds": away_odds, "fixture": match_name, "team": away_name})
        diff = abs(home_odds - away_odds)
        if diff < most_competitive["diff"]: most_competitive.update({"diff": diff, "fixture": match_name})

    # 4. Return structured data
    if safest_bet["fixture"] is None:
        return {"error": f"Found matches for '{date_query}', but couldn't analyze their odds."}

    return {
        "start_date": start_date, "end_date": end_date,
        "safest_bet": safest_bet, "riskiest_bet": riskiest_bet,
        "most_competitive_match": most_competitive
    }

# --- Fixture & Team Tools ---

@tool
def get_fixtures_by_date(date_query: str):
    """
    Use this tool to find all matches on a specific or relative date.
    It can understand queries like "tomorrow", "Sunday", "next Friday", or a specific date like "September 22nd".
    Do not use this for questions about a specific team.
    """
    logging.info(f"--- Running get_fixtures_by_date for date query: '{date_query}' ---")
    
    # Set a UTC-aware relative base to avoid timezone issues with "tomorrow"
    today_utc = datetime.now(timezone.utc)
    date_settings = {
        'TIMEZONE': 'UTC', 
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future',
        'RELATIVE_BASE': today_utc 
    }
    parsed_date = dateparser.parse(date_query, settings=date_settings)
    
    if not parsed_date:
        return f"I'm sorry, I couldn't understand the date '{date_query}'. Please try again with a clearer date."

    target_date = parsed_date.date()
    logging.info(f"Date parser converted '{date_query}' to UTC date: {target_date}")

    response = api_client.get_fixtures_by_sport(sport_id=1)
    if not response:
        return "Error: Could not retrieve fixtures from the API."

    fixtures_list = response.get("data") if isinstance(response, dict) else response
    if not fixtures_list or not isinstance(fixtures_list, list):
        return "No fixtures data was found for the given date."

    date_fixtures = []
    for f in fixtures_list:
        fixture_date_str = f.get("fixture_date")
        start_time_str = f.get("startTime")

        if not fixture_date_str and not start_time_str:
            continue

        fixture_datetime = None
        try:
            if fixture_date_str:
                fixture_datetime = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00"))
            elif start_time_str:
                current_year = datetime.now().year
                full_date_str = f"{current_year}-{start_time_str}"
                fixture_datetime = datetime.strptime(full_date_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            
            if fixture_datetime and fixture_datetime.date() == target_date:
                f['parsed_datetime'] = fixture_datetime
                date_fixtures.append(f)

        except (ValueError, TypeError) as e:
            logging.warning(f"Could not parse date for fixture {f.get('id')} in get_fixtures_by_date: {e}")
            continue
    
    if not date_fixtures:
        return f"No matches found for {date_query}."

    date_fixtures.sort(key=lambda x: x.get("parsed_datetime"))

    formatted_output = []
    for f in date_fixtures:
        home = f.get("home_team_data", {}).get("name", {}).get("en", "N/A")
        away = f.get("away_team_data", {}).get("name", {}).get("en", "N/A")
        tournament = f.get("tournament_name", {}).get("en", "N/A")
        match_time = f.get("parsed_datetime").strftime("%H:%M UTC")
        # Put time at the front to make it more prominent for the LLM
        formatted_output.append(f"- {match_time}: {home} vs {away} ({tournament})")
    
    logging.info(f"--- get_fixtures_by_date finished successfully, found {len(formatted_output)} matches. ---")
    return f"Here are the matches for {target_date.strftime('%A, %B %d')}:\\n" + "\\n".join(formatted_output)

@tool
def find_team_fixture(team_name: str, competition_name: Optional[str] = None):
    """
    Use this to find upcoming matches for a sports team. This is the primary tool for any question related to a team's schedule.
    You can optionally filter by a specific competition if the user mentions one.
    Examples:
    - User: "When does Barcelona play?" -> Call with team_name="Barcelona"
    - User: "Any Champions League matches for Real Madrid soon?" -> Call with team_name="Real Madrid", competition_name="Champions League"
    """
    logging.info(f"--- Running find_team_fixture for team: '{team_name}', competition: '{competition_name}' ---")

    # Step 1: Find the best match for the team name using fuzzy matching
    all_teams = team_name_cache.get_all_team_names()
    if not all_teams:
        return "Sorry, the team list is currently unavailable. Please try again in a moment."

    best_match, score = process.extractOne(team_name, all_teams)
    MATCH_THRESHOLD = 80
    if score < MATCH_THRESHOLD:
        logging.warning(f"No good match for '{team_name}'. Best guess: '{best_match}' (Score: {score}).")
        return f"I couldn't find a team that closely matches '{team_name}'. Could you try a different name?"

    logging.info(f"Fuzzy match found for team: '{team_name}' -> '{best_match}' (Score: {score})")
    corrected_team_name = best_match

    # Step 2: Get all upcoming fixtures for the corrected team name
    response = api_client.get_fixtures_by_sport(sport_id=1)
    if not response:
        return "Error: Could not retrieve fixtures from the API."

    fixtures_list = response.get("data") if isinstance(response, dict) else response
    if not fixtures_list or not isinstance(fixtures_list, list):
        return f"No fixtures data was found for {corrected_team_name}."

    team_fixtures = []
    today = datetime.now(timezone.utc).date()

    for f in fixtures_list:
        fixture_date_str = f.get("fixture_date")
        start_time_str = f.get("startTime")

        if not fixture_date_str and not start_time_str:
            continue

        fixture_datetime = None
        try:
            if fixture_date_str:
                fixture_datetime = datetime.fromisoformat(fixture_date_str.replace("Z", "+00:00"))
            elif start_time_str:
                current_year = datetime.now().year
                full_date_str = f"{current_year}-{start_time_str}"
                fixture_datetime = datetime.strptime(full_date_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)

            if not fixture_datetime:
                continue

            fixture_date = fixture_datetime.date()
            
            home_team = f.get("home_team_data", {}).get("name", {}).get("en")
            away_team = f.get("away_team_data", {}).get("name", {}).get("en")

            is_match = (
                fixture_date >= today and
                (corrected_team_name == home_team or corrected_team_name == away_team)
            )

            if is_match:
                f['parsed_datetime'] = fixture_datetime
                team_fixtures.append(f)
        except (ValueError, TypeError) as e:
            logging.warning(f"Could not parse date for fixture {f.get('id')}: {e}")
            continue
            
    # Step 3: Optional - Filter by competition name if provided
    if competition_name:
        logging.info(f"Filtering fixtures by competition: '{competition_name}'")
        filtered_by_competition = []
        for f in team_fixtures:
            tournament_name = f.get("tournament_name", {}).get("en", "")
            # Using partial_ratio for better matching (e.g., "champions" vs "Champions League")
            if fuzz.partial_ratio(competition_name.lower(), tournament_name.lower()) > 85:
                filtered_by_competition.append(f)
        
        team_fixtures = filtered_by_competition
        logging.info(f"Found {len(team_fixtures)} fixtures after competition filter.")


    if not team_fixtures:
        if competition_name:
            return f"No upcoming fixtures found for {corrected_team_name} in {competition_name}."
        return f"No upcoming fixtures found for {corrected_team_name}."

    team_fixtures.sort(key=lambda x: x.get("parsed_datetime"))
    
    # Step 4: Format the output for readability
    formatted_fixtures = []
    for f in team_fixtures[:5]: # Limit to the next 5
        home = f.get("home_team_data", {}).get("name", {}).get("en", "N/A")
        away = f.get("away_team_data", {}).get("name", {}).get("en", "N/A")
        tournament = f.get("tournament_name", {}).get("en", "N/A")
        
        date_obj = f.get('parsed_datetime')
        if date_obj:
            formatted_date = date_obj.strftime("%A, %B %d at %H:%M UTC")
        else:
            formatted_date = f.get("fixture_date") or f.get("startTime") or "N/A"

        formatted_fixtures.append(
            f"{home} vs {away} in the {tournament} on {formatted_date}"
        )

    logging.info(f"--- find_team_fixture finished successfully. ---")
    return "\n".join(formatted_fixtures)

@tool
def get_teams_by_tournament(tournament_name: str):
    """
    Use this tool to find all the teams participating in a specific tournament.
    It can understand variations in tournament names, like "Champions League".
    """
    logging.info(f"--- Running get_teams_by_tournament for tournament query: '{tournament_name}' ---")
    
    # Step 1: Use the cache to find the canonical tournament name and its unique ID
    football_tournaments_map = tournament_name_cache.get_all_tournaments_map()
    if not football_tournaments_map:
        return "Sorry, the list of available tournaments is currently empty."

    tournament_names = list(football_tournaments_map.keys())
    best_match, score = process.extractOne(tournament_name, tournament_names)
    
    MATCH_THRESHOLD = 90
    if score < MATCH_THRESHOLD:
        return f"I couldn't find a tournament that closely matches '{tournament_name}'."
    
    corrected_tournament_name = best_match
    matched_tournament_id = football_tournaments_map[corrected_tournament_name]
    logging.info(f"Fuzzy match found: '{tournament_name}' -> '{corrected_tournament_name}' (ID: {matched_tournament_id}, Score: {score})")
    
    # Step 2: Fetch ALL football fixtures to be filtered by ID
    all_fixtures_response = api_client.get_fixtures_by_sport(sport_id=1)
    if not all_fixtures_response:
        return "Error: Could not retrieve match data from the API."

    fixtures_list = all_fixtures_response.get("data") if isinstance(all_fixtures_response, dict) else all_fixtures_response
    if not fixtures_list or not isinstance(fixtures_list, list):
        return f"No match data was found to search for teams."

    # Step 3: Filter fixtures by the matched tournament ID
    teams_in_tournament = set()
    for f in fixtures_list:
        if f.get("tournament_id") == matched_tournament_id:
            home_team = f.get("home_team_data", {}).get("name", {}).get("en")
            away_team = f.get("away_team_data", {}).get("name", {}).get("en")
            if home_team:
                teams_in_tournament.add(home_team)
            if away_team:
                teams_in_tournament.add(away_team)
    
    if not teams_in_tournament:
        return f"Found the tournament '{corrected_tournament_name}', but it appears to have no teams playing in it at the moment. It might be between seasons."

    sorted_teams = sorted(list(teams_in_tournament))
    logging.info(f"--- get_teams_by_tournament finished successfully. Found {len(sorted_teams)} teams. ---")
    
    return f"The teams in {corrected_tournament_name} are: {', '.join(sorted_teams)}."

# --- Odds & Analysis Tools ---

@tool
def get_daily_odds_analysis(date_query: str) -> str:
    """
    Use this tool for broad questions about betting odds for a specific day or date range, like "Which team has the best odds today?", "What is the safest bet for this weekend?", or "Find the most competitive match this month".
    It analyzes all matches on a given day/range to find the safest bet, the riskiest (highest reward) bet, and the most competitive match.
    Understands "today", "tomorrow", "this weekend", "this month", "end of the month".
    """
    logging.info(f"--- Running get_daily_odds_analysis for date query: '{date_query}' ---")
    analysis_result = _analyze_daily_odds(date_query)
    if "error" in analysis_result: return analysis_result["error"]
    
    # Format the structured result into a user-friendly string
    start_date = analysis_result["start_date"]; end_date = analysis_result["end_date"]
    safest_bet = analysis_result["safest_bet"]; riskiest_bet = analysis_result["riskiest_bet"]
    most_competitive = analysis_result["most_competitive_match"]
    if start_date == end_date: date_str = start_date.strftime('%A, %B %d')
    else: date_str = f"the period from {start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}"
    response_parts = [f"Here is the betting analysis for {date_str}:"]
    if safest_bet["fixture"]: response_parts.append(f"- Safest Bet: {safest_bet['team']} to win in '{safest_bet['fixture']}' with odds of {safest_bet['odds']}.")
    if riskiest_bet["fixture"]: response_parts.append(f"- Highest Reward Bet: {riskiest_bet['team']} to win in '{riskiest_bet['fixture']}' with odds of {riskiest_bet['odds']}.")
    if most_competitive["fixture"]: 
        explanation = f"This is the most competitive match because the odds are very close, with a difference of only {most_competitive['diff']:.2f}."
        response_parts.append(f"- Most Competitive Match: '{most_competitive['fixture']}'. {explanation}")
        
    return "\n".join(response_parts)

@tool
def get_odds_for_match(team_one: str, team_two: str) -> str:
    """
    Use this tool when a user asks for odds on a specific match between two teams.
    This tool finds the upcoming fixture and retrieves all available odds (home win, away win, draw).
    It returns a JSON string with the odds information.
    """
    logging.info(f"--- Running get_odds_for_match for: '{team_one}' vs '{team_two}' ---")
    odds_data = _get_match_odds_data(team_one, team_two)
    return json.dumps(odds_data)

@tool
def get_odds_for_outcome(team_one: str, team_two: str, outcome: str) -> str:
    """
    Use this tool when a user asks for the odds of a specific outcome in a match, but does NOT provide an amount to bet. For example: "How much does a draw pay for Napoli vs Pisa?".
    The 'outcome' parameter must be one of 'home_win', 'away_win', or 'draw'.
    """
    logging.info(f"--- Running get_odds_for_outcome for {team_one} vs {team_two}, outcome: {outcome} ---")
    
    odds_data = _get_match_odds_data(team_one, team_two)
    if "error" in odds_data:
        return f"I couldn't find the odds. Reason: {odds_data['error']}"

    odds_value = None
    outcome_map = {
        "draw": "draw",
        "home_win": "home_win",
        "away_win": "away_win"
    }
    
    lookup_key = outcome_map.get(outcome)
    if lookup_key:
        odds_value = odds_data.get("match_result", {}).get(lookup_key)
        
    if odds_value is not None:
        # We need to find the specific team name for home_win/away_win for the response
        outcome_str = outcome.replace('_', ' ')
        if "win" in outcome_str:
             # Extract the winner's name from the full match string for a more natural response
             match_str = odds_data.get('match', f'{team_one} vs {team_two}')
             winner_name = team_one if fuzz.partial_ratio(team_one.lower(), match_str.lower().split(' vs ')[0]) > 80 else team_two
             outcome_str = f"a {winner_name} win"

        return f"The odds for {outcome_str} in the {odds_data.get('match')} match are {odds_value}."
    else:
        return f"I found the match, but I couldn't find the specific odds for the outcome '{outcome}'."

# --- User Management and Betting Tools ---

@tool
def get_user_balance():
    """
    Returns the default user's current balance by calling the API.
    """
    balance_data = api_client.get_user_balance()
    if not balance_data or "money" not in balance_data:
        return "Could not retrieve balance from the API."
        
    balance = balance_data["money"]
    return f"Your current balance is ${balance:.2f}."

@tool
def place_real_bet(fixture_id: int, tournament_id: str, bet_on_team_name: str, bet_type: str, amount: float):
    """
    Places a real bet for a specific fixture and outcome through the API for the default user.
    'bet_on_team_name' is the name of the team to bet on.
    'bet_type' must be 'Home', 'Away', or 'Draw'.
    'amount' is the value of the bet.
    This action is final and will use the user's real balance.
    """
    # First, get current balance to check if the user has enough funds
    balance_data = api_client.get_user_balance()
    if not balance_data or "money" not in balance_data:
        return "Could not verify user balance before placing bet."
    
    current_balance = balance_data["money"]
    if amount <= 0:
        return "Bet amount must be positive."
    if amount > current_balance:
        return f"Insufficient balance. You have ${current_balance:.2f} but tried to bet ${amount:.2f}."

    # Then, get odds to find the correct bet_id and odd value
    odds_data = api_client.get_odds(fixture_id=fixture_id)
    if not odds_data or not odds_data.get("data"):
        return f"Could not find odds for fixture {fixture_id} to place the bet."

    bet_id = None
    odd_value = None
    # Find the correct bet based on the team name and bet type
    home_team = odds_data["data"][0].get("home_team", "").lower()
    away_team = odds_data["data"][0].get("away_team", "").lower()

    if bet_on_team_name.lower() in home_team and bet_type == "Home":
        market_key = "Home"
    elif bet_on_team_name.lower() in away_team and bet_type == "Away":
        market_key = "Away"
    elif bet_type == "Draw":
        market_key = "Draw"
    else:
        return f"Could not match bet type '{bet_type}' with team '{bet_on_team_name}'."

    for market in odds_data["data"]:
        if market["market_name"] == "Match Winner":
            if market_key in market["odds"]:
                bet_id = market["bet_id"]
                odd_value = float(market["odds"][market_key])
                break
    
    if not bet_id or not odd_value:
        return f"Could not find a valid bet for '{bet_on_team_name}'."

    # Finally, place the bet
    response = api_client.place_bet(
        fixture_id=fixture_id,
        tournament_id=tournament_id,
        bet_id=bet_id,
        odd=odd_value,
        amount=amount
    )

    if response and response.get("status") == "success":
        winnings = amount * odd_value
        new_balance = current_balance - amount
        return f"Bet placed successfully! You bet ${amount:.2f} on {bet_on_team_name}. Potential winnings: ${winnings:.2f}. Your new balance is approximately ${new_balance:.2f}."
    else:
        return f"Failed to place bet. API responded with: {response}"

@tool
def calculate_winnings_for_match(team_one: str, team_two: str, amount: float, bet_on: str) -> str:
    """
    Use this tool to calculate potential winnings for a bet on a specific match.
    You need the two teams, the amount to bet, and what the user is betting on.
    The 'bet_on' parameter should be one of 'home_win', 'away_win', or 'draw'.
    """
    logging.info(f"--- Running calculate_winnings_for_match for {team_one} vs {team_two} ---")
    
    # Step 1: Get the odds data using the new helper function
    odds_data = _get_match_odds_data(team_one, team_two)
    if "error" in odds_data:
        return f"I couldn't calculate the winnings because I couldn't find the odds. Reason: {odds_data['error']}"

    # Step 2: Extract the correct odds based on the 'bet_on' parameter
    odds_value = None
    if bet_on == "draw":
        odds_value = odds_data.get("match_result", {}).get("draw")
    elif bet_on == "home_win":
        odds_value = odds_data.get("match_result", {}).get("home_win")
    elif bet_on == "away_win":
        odds_value = odds_data.get("match_result", {}).get("away_win")
        
    if odds_value is None:
        return f"I found the match, but I couldn't find the specific odds for '{bet_on}'."

    # Step 3: Perform calculation and format the response string
    winnings = amount * odds_value
    total_return = winnings + amount
    
    # Use robust HTML tags for formatting.
    response = [
        f"The odds for a {bet_on.replace('_', ' ')} in the {odds_data.get('match', 'match')} are <b>{odds_value}</b>.",
        f"If you bet <b>${amount:.2f}</b> and win, your total winnings would be <b>${winnings:.2f}</b>.",
        f"Your total return would be <b>${total_return:.2f}</b> (your ${winnings:.2f} winnings + your ${amount:.2f} stake)."
    ]
    return "<br><br>".join(response)

@tool
def get_match_recommendation():
    """
    Use this tool when a user asks for a match recommendation but does NOT provide a betting amount.
    This tool finds the safest bet for today and suggests it to the user.
    """
    logging.info(f"--- Running get_match_recommendation ---")
    analysis_result = _analyze_daily_odds("today")
    if "error" in analysis_result:
        return f"I can't provide a recommendation right now. Reason: {analysis_result['error']}"
    
    safest_bet = analysis_result.get("safest_bet")
    if not safest_bet or not safest_bet.get("fixture"):
        return "I couldn't find a clear match to recommend for today."
        
    recommendation = (
        f"Based on today's matches, the safest bet appears to be on "
        f"<b>{safest_bet['team']}</b> to win in the match '{safest_bet['fixture']}' "
        f"with odds of <b>{safest_bet['odds']}</b>."
    )
    return recommendation

@tool
def get_betting_recommendation(amount: float) -> str:
    """
    Use this tool when a user asks for a betting recommendation with a specific amount of money, like "What can I bet with $100?".
    This tool automatically analyzes TODAY'S matches to provide a 60/40 split betting strategy. Do not ask the user for a date.
    """
    logging.info(f"--- Running get_betting_recommendation for amount: ${amount} ---")
    if amount <= 0: return "The amount to bet must be positive."
    analysis_result = _analyze_daily_odds("today")
    if "error" in analysis_result:
        return f"I can't provide a recommendation right now because I couldn't analyze today's matches. Reason: {analysis_result['error']}"
    safest_bet = analysis_result.get("safest_bet")
    riskiest_bet = analysis_result.get("riskiest_bet")
    if not safest_bet or not riskiest_bet or not safest_bet.get("fixture") or not riskiest_bet.get("fixture"):
        return "I couldn't find a clear low-risk and high-risk bet for today to create a recommendation."
    low_risk_amount = amount * 0.60
    high_risk_amount = amount * 0.40
    low_risk_winnings = low_risk_amount * safest_bet["odds"]
    high_risk_winnings = high_risk_amount * riskiest_bet["odds"]
    
    # Use robust HTML tags for formatting to ensure proper rendering in Streamlit.
    recommendation = [
        f"With ${amount}, here is a balanced betting strategy for today:",
        f"<b>Low-Risk Bet (60%):</b> Bet <b>${low_risk_amount:.2f}</b> on <b>{safest_bet['team']}</b> to win in the match '{safest_bet['fixture']}'.<br>  - Odds: <b>{safest_bet['odds']}</b><br>  - Potential Winnings: <b>${low_risk_winnings:.2f}</b>",
        f"<b>High-Risk Bet (40%):</b> Bet <b>${high_risk_amount:.2f}</b> on <b>{riskiest_bet['team']}</b> to win in the match '{riskiest_bet['fixture']}'.<br>  - Odds: <b>{riskiest_bet['odds']}</b><br>  - Potential Winnings: <b>${high_risk_winnings:.2f}</b>"
    ]
    return "<br><br>".join(recommendation)

