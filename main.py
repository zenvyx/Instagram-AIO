import os
import time
import random
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, 
    TwoFactorRequired, ClientError
)
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich.align import Align
from rich.progress import Progress
from rich.markdown import Markdown
import textwrap
from typing import List, Dict, Optional
from logging import Logger
from datetime import datetime 
import os
import sys
import ctypes
import hashlib
import time
from keyauth import api
from getpass import getpass
from colorama import Fore, init

# Initialize colors
init(autoreset=True)

logger = Logger("IG AIO")

console = Console()

class Config:
    def __init__(self):
        self.config_path = "assets/config.json"
        self.default_config = {
            "delays": {
                "follow": 10,
                "unfollow": 10,
                "dm": 20,
                "like": 2,
                "comment": 3,
                "story_view": 1,
                "between_actions": 1,
                "scrape": 5
            },
            "debug": True,
            "max_attempts": 3,
            "safe_mode": True,
            "dm_daily_limit": 50,
            "like_limit": 300,
            "comment_limit": 100,
            "follow_limit": 200,
            "scrape_likes_mode": 0,  # 0 = all posts, 1 = recent only
            "location_posts_limit": 20,  # Number of freshest posts to scrape from locations
            "max_posts_to_scrape": 20,  # Default to 20 posts if not specified
            "max_following_limit": 7500,  # Maximum number of accounts an account can follow
            "max_threads": 5  # Maximum threads for multi-threading
        }
        self.load_config()

    def load_config(self):
        os.makedirs("assets", exist_ok=True)
        if not os.path.exists(self.config_path):
            self.save_config()
            return self.default_config
        
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                for key in self.default_config:
                    if key not in config:
                        config[key] = self.default_config[key]
                return config
        except Exception as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            return self.default_config

    def save_config(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.default_config, f, indent=4)
        except Exception as e:
            console.print(f"[red]Error saving config: {e}[/red]")

    @property
    def delays(self):
        return self.load_config().get("delays", self.default_config["delays"])
    
    @property
    def debug(self):
        return self.load_config().get("debug", self.default_config["debug"])
    
    @property
    def max_attempts(self):
        return self.load_config().get("max_attempts", self.default_config["max_attempts"])
    
    @property
    def safe_mode(self):
        return self.load_config().get("safe_mode", self.default_config["safe_mode"])
    
    @property
    def dm_daily_limit(self):
        return self.load_config().get("dm_daily_limit", self.default_config["dm_daily_limit"])
    
    @property
    def like_limit(self):
        return self.load_config().get("like_limit", self.default_config["like_limit"])
    
    @property
    def comment_limit(self):
        return self.load_config().get("comment_limit", self.default_config["comment_limit"])
    
    @property
    def follow_limit(self):
        return self.load_config().get("follow_limit", self.default_config["follow_limit"])
    
    @property
    def scrape_likes_mode(self):
        return self.load_config().get("scrape_likes_mode", self.default_config["scrape_likes_mode"])
    
    @property
    def location_posts_limit(self):
        return self.load_config().get("location_posts_limit", self.default_config["location_posts_limit"])
    
    @property
    def max_posts_to_scrape(self):
        return self.load_config().get("max_posts_to_scrape", 20)  # Default to 20 posts if not specified
    
    @property
    def max_following_limit(self):
        return self.load_config().get("max_following_limit", self.default_config["max_following_limit"])
    
    @property
    def max_threads(self):
        return self.load_config().get("max_threads", self.default_config["max_threads"])

class InstagramClient:
    def __init__(self, username: str, password: str = None, proxy: Optional[str] = None, sessionid: Optional[str] = None):
        self.config = Config()
        self.client = Client()
        self.username = username
        self.password = password
        self.sessionid = sessionid
        self.proxy = proxy
        self.login_success = False
        self.last_action = time.time()
        self.dm_count_today = 0
        self.like_count_today = 0
        self.comment_count_today = 0
        self.follow_count_today = 0
        self.last_action_date = None
        
        self.setup_client()
        if self.sessionid:
            self.login_with_sessionid()
        else:
            self.login()

    def setup_client(self):
        self.client.delay_range = [1, 3]
        self.client.set_locale("en_US")
        self.client.set_country("US")
        self.client.set_timezone_offset(-18000)
        
        if self.proxy:
            try:
                self.client.set_proxy(self.proxy)
                if self.config.debug:
                    console.print(f"[yellow][Proxy Set][/yellow] for {self.username}")
            except Exception as e:
                console.print(f"[red]Proxy Error for {self.username}: {e}[/red]")

    def login(self):
        try:
            if self.config.debug:
                console.print(f"[yellow]Attempting login for {self.username}...[/yellow]")
            
            session_file = f"sessions/{self.username}.json"
            if os.path.exists(session_file):
                try:
                    self.client.load_settings(session_file)
                    if self.config.debug:
                        console.print(f"[blue]Loaded session for {self.username}[/blue]")
                except Exception as e:
                    if self.config.debug:
                        console.print(f"[yellow]Session load failed: {e}[/yellow]")

            login_result = self.client.login(self.username, self.password)
            
            if login_result:
                self.login_success = True
                console.print(f"[green]Login success for {self.username}![/green]")
                os.makedirs("sessions", exist_ok=True)
                self.client.dump_settings(session_file)
            else:
                console.print(f"[red]Login failed for {self.username} (no error)[/red]")
                
        except TwoFactorRequired:
            self.handle_two_factor()
        except ChallengeRequired:
            self.handle_challenge()
        except LoginRequired:
            console.print(f"[red]Login required for {self.username} (session expired)[/red]")
        except ClientError as e:
            console.print(f"[red]Client Error for {self.username}: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Unexpected error for {self.username}: {e}[/red]")

    def login_with_sessionid(self):
        try:
            if self.config.debug:
                console.print(f"[yellow]Attempting session ID login for {self.username}...[/yellow]")
            
            session_file = f"sessions/{self.username}.json"
            if os.path.exists(session_file):
                try:
                    self.client.load_settings(session_file)
                    if self.config.debug:
                        console.print(f"[blue]Loaded session for {self.username}[/blue]")
                except Exception as e:
                    if self.config.debug:
                        console.print(f"[yellow]Session load failed: {e}[/yellow]")

            # Set session ID directly
            self.client.set_settings({
                "cookies": {
                    "sessionid": self.sessionid,
                    "ds_user_id": self.username  # This is a placeholder, actual user ID will be fetched
                }
            })
            
            # Verify session by getting user info
            user_info = self._safe_request(self.client.account_info)
            if user_info:
                self.login_success = True
                console.print(f"[green]Session ID login success for {self.username}![/green]")
                os.makedirs("sessions", exist_ok=True)
                self.client.dump_settings(session_file)
            else:
                console.print(f"[red]Session ID login failed for {self.username}[/red]")
                
        except Exception as e:
            console.print(f"[red]Session ID login error for {self.username}: {e}[/red]")

    def handle_two_factor(self):
        console.print(f"[yellow]2FA required for {self.username}[/yellow]")
        code = Prompt.ask("Enter 2FA code")
        try:
            self.client.two_factor_login(code)
            self.login_success = True
            console.print(f"[green]2FA login success for {self.username}![/green]")
        except Exception as e:
            console.print(f"[red]2FA failed: {e}[/red]")

    def handle_challenge(self):
        console.print(f"[yellow]Challenge required for {self.username}[/yellow]")
        try:
            self.client.challenge_resolve(self.client.last_json)
            self.login_success = True
            console.print(f"[green]Challenge passed for {self.username}![/green]")
        except Exception as e:
            console.print(f"[red]Challenge failed: {e}[/red]")

    def is_active(self) -> bool:
        return self.login_success

    def update_daily_counts(self):
        today = time.strftime("%Y-%m-%d")
        if self.last_action_date != today:
            self.dm_count_today = 0
            self.like_count_today = 0
            self.comment_count_today = 0
            self.follow_count_today = 0
            self.last_action_date = today

    def can_send_dm(self) -> bool:
        self.update_daily_counts()
        return self.dm_count_today < self.config.dm_daily_limit

    def can_like(self) -> bool:
        self.update_daily_counts()
        return self.like_count_today < self.config.like_limit
    
    def can_comment(self) -> bool:
        self.update_daily_counts()
        return self.comment_count_today < self.config.comment_limit
    
    def can_follow(self) -> bool:
        self.update_daily_counts()
        return self.follow_count_today < self.config.follow_limit

    def _safe_request(self, func, *args, **kwargs):
        attempts = 0
        max_attempts = self.config.max_attempts
        
        while attempts < max_attempts:
            try:
                if not self.login_success:
                    if self.config.debug:
                        console.print(f"[red]{self.username}: Session not active[/red]")
                    return None
                    
                elapsed = time.time() - self.last_action
                min_delay = self.config.delays["between_actions"]
                if elapsed < min_delay:
                    delay = min_delay - elapsed
                    if self.config.debug:
                        console.print(f"[yellow]Waiting {delay:.1f}s between actions[/yellow]")
                    time.sleep(delay)
                    
                result = func(*args, **kwargs)
                self.last_action = time.time()
                return result
                
            except LoginRequired:
                console.print(f"[red]{self.username}: Login required[/red]")
                self.login_success = False
                break
            except ChallengeRequired:
                console.print(f"[yellow]{self.username}: Challenge required[/yellow]")
                try:
                    self.client.challenge_resolve(self.client.last_json)
                    continue
                except Exception as e:
                    console.print(f"[red]Challenge failed: {e}[/red]")
                    self.login_success = False
                    break
            except Exception as e:
                attempts += 1
                console.print(f"[red]{self.username}: Attempt {attempts}/{max_attempts} failed - {e}[/red]")
                if "rate limited" in str(e).lower():
                    time.sleep(60)
                if attempts >= max_attempts:
                    if self.config.safe_mode:
                        console.print(f"[red]Max attempts reached, skipping...[/red]")
                        return None
                    else:
                        raise
                time.sleep(5)
        return None

    def view_stories(self, usernames: List[str]):
        """View stories of given usernames"""
        def process_story(client, username):
            try:
                if client.config.debug:
                    console.print(f"[yellow]{client.username}: Viewing {username}'s stories...[/yellow]")
                    
                uid = client._safe_request(client.client.user_id_from_username, username)
                if not uid:
                    return
                    
                stories = client._safe_request(client.client.user_stories, uid)
                if not stories:
                    if client.config.debug:
                        console.print(f"[yellow]No stories found for {username}[/yellow]")
                    return
                    
                for story in stories:
                    client._safe_request(client.client.media_seen, [story.pk])
                    
                    time.sleep(random.uniform(
                        max(0.5, client.config.delays["story_view"] - 0.5),
                        client.config.delays["story_view"] + 0.5
                    ))
                    
                console.print(f"[green]{client.username}: Viewed {username}'s stories[/green]")
                
            except Exception as e:
                console.print(f"[red]Story view error: {e}[/red]")

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            for username in usernames:
                executor.submit(process_story, self, username.strip())

    def like_recent_posts(self, username: str, count: int = 3):
        if not self.can_like():
            console.print(f"[yellow]{self.username}: Daily like limit reached ({self.like_count_today}/{self.config.like_limit})[/yellow]")
            return False
            
        try:
            uid = self._safe_request(self.client.user_id_from_username, username)
            if not uid:
                return False
                
            posts = self._safe_request(self.client.user_medias, uid, amount=count)
            if not posts:
                console.print(f"[yellow]No posts found for {username}[/yellow]")
                return False
                
            def process_post(post):
                result = self._safe_request(self.client.media_like, media_id=post.id)
                if result:
                    self.like_count_today += 1
                    console.print(f"[green]{self.username}: Liked post {post.id}[/green]")
                else:
                    console.print(f"[red]{self.username}: Failed to like post {post.id}[/red]")
                
                time.sleep(random.uniform(
                    max(0.5, self.config.delays["like"] - 0.5),
                    self.config.delays["like"] + 0.5
                ))
                
            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_post, posts)
                
            return True
            
        except Exception as e:
            console.print(f"[red]Like error for {username}: {e}[/red]")
            return False

    def mass_follow(self, usernames: List[str]):
        """Follow users from a list, removing them from the input file after successful follow"""
        # Get current following count
        try:
            current_following = self._safe_request(self.client.user_info, self.client.user_id).following_count
            if current_following >= self.config.max_following_limit:
                console.print(f"[yellow]{self.username}: Already at max following limit ({current_following}/{self.config.max_following_limit})[/yellow]")
                return
        except Exception as e:
            console.print(f"[red]Error getting following count: {e}[/red]")
            return

        remaining_follows = self.config.max_following_limit - current_following
        if remaining_follows <= 0:
            console.print(f"[yellow]{self.username}: Already at max following limit[/yellow]")
            return

        # Only process up to remaining_follows users
        usernames = usernames[:remaining_follows]
        
        def process_follow(username):
            try:
                if self.config.debug:
                    console.print(f"[yellow]{self.username}: Following {username}...[/yellow]")
                    
                uid = self._safe_request(self.client.user_id_from_username, username)
                if not uid:
                    return
                    
                result = self._safe_request(self.client.user_follow, user_id=uid)
                if result:
                    console.print(f"[green]{self.username}: Followed {username}[/green]")
                    # Remove from users.txt and add to completed_follows.txt
                    self.update_follow_files(username)
                    self.follow_count_today += 1
                else:
                    console.print(f"[red]{self.username}: Follow failed for {username}[/red]")
                    
                time.sleep(random.uniform(
                    max(1, self.config.delays["follow"] - 2),
                    self.config.delays["follow"] + 2
                ))
                
            except Exception as e:
                console.print(f"[red]Follow error: {e}[/red]")
                if "rate limited" in str(e).lower():
                    time.sleep(60)

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            executor.map(process_follow, [u.strip() for u in usernames if u.strip()])

    def mass_follow_with_limit(self, usernames: List[str], max_follows: int):
        """Follow users from a list with a maximum follow limit"""
        if not self.can_follow():
            logger.info(f"{self.username}: Daily follow limit reached ({self.follow_count_today}/{self.config.follow_limit})")
            return

        # Calculate how many follows we can still do today
        remaining_follows = min(
            self.config.follow_limit - self.follow_count_today,
            max_follows - self.client.user_info(self.client.user_id).following_count,
            len(usernames)
        )

        if remaining_follows <= 0:
            logger.info(f"{self.username}: Already at or over follow limit ({self.client.user_info(self.client.user_id).following_count}/{max_follows})")
            return

        logger.info(f"{self.username}: Attempting to follow {remaining_follows} users (current: {self.client.user_info(self.client.user_id).following_count}/{max_follows})")

        def process_follow(username):
            try:
                uid = self._safe_request(self.client.user_id_from_username, username)
                if not uid:
                    return
                        
                result = self._safe_request(self.client.user_follow, user_id=uid)
                if result:
                    self.follow_count_today += 1
                    logger.info(f"{self.username}: Followed {username} (total: {self.follow_count_today})")
                    self.update_follow_files(username)
                else:
                    logger.error(f"{self.username}: Follow failed for {username}")
                        
                time.sleep(random.uniform(
                    max(1, self.config.delays["follow"] - 2),
                    self.config.delays["follow"] + 2
                ))
                    
            except Exception as e:
                logger.error(f"Follow error: {e}")
                if "rate limited" in str(e).lower():
                    time.sleep(60)

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            executor.map(process_follow, random.sample(usernames, remaining_follows))

    def update_follow_files(self, username: str):
        """Remove username from users.txt and add to completed_follows.txt"""
        users_file = "assets/users.txt"
        completed_file = "assets/completed_follows.txt"
        
        # Read current users
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                users = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            console.print(f"[red]Users file not found: {users_file}[/red]")
            return
            
        # Remove the followed user
        if username in users:
            users.remove(username)
            
            # Write back the updated list
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(users))
            except Exception as e:
                console.print(f"[red]Error updating users file: {e}[/red]")
                return
                
        # Add to completed follows
        try:
            os.makedirs("assets", exist_ok=True)
            with open(completed_file, "a", encoding="utf-8") as f:
                f.write(f"{username}\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update completed follows: {e}[/yellow]")

    def mass_unfollow(self, usernames: List[str]):
        """Unfollow users from a list, removing them from the input file after successful unfollow"""
        def process_unfollow(username):
            try:
                if self.config.debug:
                    console.print(f"[yellow]{self.username}: Unfollowing {username}...[/yellow]")
                    
                uid = self._safe_request(self.client.user_id_from_username, username)
                if not uid:
                    return
                    
                result = self._safe_request(self.client.user_unfollow, user_id=uid)
                if result:
                    console.print(f"[green]{self.username}: Unfollowed {username}[/green]")
                    # Remove from users.txt and add to completed_unfollows.txt
                    self.update_unfollow_files(username)
                else:
                    console.print(f"[red]{self.username}: Unfollow failed for {username}[/red]")
                    
                time.sleep(random.uniform(
                    max(1, self.config.delays["unfollow"] - 2),
                    self.config.delays["unfollow"] + 2
                ))
                
            except Exception as e:
                console.print(f"[red]Unfollow error: {e}[/red]")
                if "rate limited" in str(e).lower():
                    time.sleep(60)

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            executor.map(process_unfollow, [u.strip() for u in usernames if u.strip()])

    def update_unfollow_files(self, username: str):
        """Remove username from users.txt and add to completed_unfollows.txt"""
        users_file = "assets/users.txt"
        completed_file = "assets/completed_unfollows.txt"
        
        # Read current users
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                users = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            console.print(f"[red]Users file not found: {users_file}[/red]")
            return
            
        # Remove the unfollowed user (if present)
        if username in users:
            users.remove(username)
            
            # Write back the updated list
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(users))
            except Exception as e:
                console.print(f"[red]Error updating users file: {e}[/red]")
                return
                
        # Add to completed unfollows
        try:
            os.makedirs("assets", exist_ok=True)
            with open(completed_file, "a", encoding="utf-8") as f:
                f.write(f"{username}\n")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update completed unfollows: {e}[/yellow]")

    def send_dm(self, username: str, message: str) -> bool:
        if not self.can_send_dm():
            console.print(f"[yellow]{self.username}: Daily DM limit reached ({self.dm_count_today}/{self.config.dm_daily_limit})[/yellow]")
            return False
            
        try:
            uid = self._safe_request(self.client.user_id_from_username, username)
            if not uid:
                return False
                
            info = self._safe_request(self.client.user_info, uid)
            if not info:
                return False
                
            name = info.full_name.split()[0] if info.full_name else username
            personalized_msg = message.replace("{name}", name)
            
            # Use direct_send with the correct parameter name
            result = self._safe_request(self.client.direct_send, text=personalized_msg, user_ids=[uid])
            if result:
                self.dm_count_today += 1
                console.print(f"[green]{self.username}: DM sent to {username}[/green]")
                return True
            return False
            
        except Exception as e:
            console.print(f"[red]DM error for {username}: {e}[/red]")
            return False

    def load_random_message(self) -> str:
        """Load a random message from assets/comments.txt or assets/message.txt"""
        message_files = ["assets/message.txt"]
        messages = []
        
        for file_path in message_files:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    file_messages = [line.strip() for line in f if line.strip()]
                    messages.extend(file_messages)
        
        if not messages:
            return "Hey! Just wanted to say hi 👋"
        
        base_msg = random.choice(messages)
        
        # Add some variations to the message
        variations = [
            ("", ""),
            (" 😊", ""),
            ("!", ""),
            ("", " Hope you're doing well!"),
            ("", " Have a great day!"),
            (" 👋", ""),
            ("", " Let me know what you think!"),
            ("", " Would love to hear your thoughts!"),
        ]
        
        prefix, suffix = random.choice(variations)
        return f"{base_msg}{prefix}{suffix}"

    def load_spintax_message(self) -> str:
        """Load a random spintax message from assets/message.txt"""
        try:
            with open("assets/message.txt", "r", encoding="utf-8") as f:
                messages = [line.strip() for line in f if line.strip()]
            
            if not messages:
                return "Hey! Just wanted to say hi 👋"
            
            return random.choice(messages)
        
        except FileNotFoundError:
            return "Hey {name}! Just wanted to say hi 👋"
        except Exception:
            return "Hello {name}! Hope you're doing well!"

    def mass_dm(self, target_file: str):
        """Send DMs using multi-line message template with controlled logging"""
        # Validate input file
        if not os.path.exists(target_file):
            console.print(f"[red]Target file not found: {target_file}[/red]")
            return
        
        # Load targets
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                target_users = [line.strip() for line in f if line.strip()]
        except Exception as e:
            console.print(f"[red]Error reading target file: {e}[/red]")
            return

        if not target_users:
            console.print("[yellow]No valid usernames found in target file[/yellow]")
            return

        # Load message template
        try:
            with open("assets/message.txt", "r", encoding="utf-8") as f:
                message_template = f.read().strip()
        except Exception as e:
            message_template = """Hello {name},

    I came across your profile and wanted to connect.

    Looking forward to hearing from you.

    Best regards"""
            console.print(f"[yellow]Using default message template: {e}[/yellow]")

        # Prepare tracking files
        messaged_file = os.path.join(os.path.dirname(target_file), "messaged_users.txt")
        completed_file = os.path.join(os.path.dirname(target_file), "completed_dms.txt")
        
        # Load already messaged users
        messaged_users = set()
        if os.path.exists(messaged_file):
            try:
                with open(messaged_file, "r", encoding="utf-8") as f:
                    messaged_users.update(line.strip() for line in f if line.strip())
            except Exception as e:
                console.print(f"[yellow]Error loading messaged users: {e}[/yellow]")

        users_to_message = [u for u in target_users if u not in messaged_users]
        
        if not users_to_message:
            console.print("[green]All users in this file have already been messaged[/green]")
            return
            
        successful_dms = 0
        failed_dms = 0
        skipped_dms = 0

        def process_dm(username):
            nonlocal successful_dms, failed_dms, skipped_dms
            if not self.can_send_dm():
                skipped_dms += 1
                console.print(f"[yellow]Daily limit reached ({self.dm_count_today}/{self.config.dm_daily_limit})[/yellow]")
                return

            try:
                # Get user info
                uid = self._safe_request(self.client.user_id_from_username, username)
                if not uid:
                    failed_dms += 1
                    return
                    
                info = self._safe_request(self.client.user_info, uid)
                if not info:
                    failed_dms += 1
                    return

                # Format message
                name = info.full_name.split()[0] if info.full_name else username
                message = message_template.replace("{name}", name)

                # Send DM
                result = self._safe_request(self.client.direct_send, 
                                        text=message, 
                                        user_ids=[uid])

                if result:
                    successful_dms += 1
                    self.dm_count_today += 1
                    with open(messaged_file, "a", encoding="utf-8") as f:
                        f.write(f"{username}\n")
                    with open(completed_file, "a", encoding="utf-8") as f:
                        f.write(f"{username}\n")
                else:
                    failed_dms += 1

                # Random delay
                time.sleep(random.uniform(
                    max(1, self.config.delays["dm"] - 2),
                    self.config.delays["dm"] + 2
                ))
                
            except Exception:
                failed_dms += 1

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            list(executor.map(process_dm, users_to_message))
        
        # Final report in your preferred format
        console.print(f"\n[bold]DM Campaign Results:[/bold]")
        console.print(f"Successful DMs: [green]{successful_dms}[/green]")
        console.print(f"Failed DMs: [red]{failed_dms}[/red]")
        console.print(f"Skipped (limit reached): [yellow]{skipped_dms}[/yellow]")

    def mass_comment_like(self, target_username: str):
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Starting mass comment/like for {target_username}[/yellow]")
                
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                return
                
            posts = self._safe_request(self.client.user_medias, uid, amount=5)
            if not posts:
                console.print(f"[yellow]No posts found for {target_username}[/yellow]")
                return
                
            def process_post(post):
                try:
                    # Like the post
                    if self.can_like():
                        like_result = self._safe_request(self.client.media_like, media_id=post.id)
                        if like_result:
                            self.like_count_today += 1
                            console.print(f"[green]{self.username}: Liked post {post.id}[/green]")
                        else:
                            console.print(f"[red]{self.username}: Failed to like post {post.id}[/red]")
                    
                    # Comment on the post
                    if self.can_comment():
                        comment_text = self.load_random_message()
                        comment_result = self._safe_request(self.client.media_comment, media_id=post.id, text=comment_text)
                        if comment_result:
                            self.comment_count_today += 1
                            console.print(f"[green]{self.username}: Commented on post {post.id}[/green]")
                        else:
                            console.print(f"[red]{self.username}: Failed to comment on post {post.id}[/red]")
                    
                    time.sleep(random.uniform(
                        max(0.5, self.config.delays["comment"] - 1),
                        self.config.delays["comment"] + 1
                    ))
                    
                except Exception as e:
                    console.print(f"[red]Post interaction error: {e}[/red]")
                    if "rate limited" in str(e).lower():
                        time.sleep(60)

            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_post, posts)
                        
        except Exception as e:
            console.print(f"[red]Mass comment/like failed: {e}[/red]")

    def engagement_summary(self, target_username: str):
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Generating engagement summary for {target_username}[/yellow]")
                
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                return
                
            info = self._safe_request(self.client.user_info, uid)
            if not info:
                return
                
            posts = self._safe_request(self.client.user_medias, uid, amount=12)
            
            console.print(f"\n[bold]Engagement Summary for {target_username}:[/bold]")
            console.print(f"Followers: {info.follower_count}")
            console.print(f"Following: {info.following_count}")
            console.print(f"Posts Analyzed: {len(posts) if posts else 0}")
            
            if posts:
                total_likes = sum(post.like_count for post in posts)
                avg_likes = total_likes / len(posts)
                engagement_rate = (avg_likes / info.follower_count) * 100 if info.follower_count > 0 else 0
                
                console.print(f"Average Likes: {avg_likes:.1f}")
                console.print(f"Engagement Rate: {engagement_rate:.2f}%")
                
                recent_post = max(posts, key=lambda p: p.taken_at)
                console.print(f"\nMost Recent Post:")
                console.print(f"Likes: {recent_post.like_count}")
                console.print(f"Comments: {recent_post.comment_count}")
                console.print(f"Posted: {recent_post.taken_at}")
            
        except Exception as e:
            console.print(f"[red]Engagement summary failed: {e}[/red]")

    def scrape_tagged_posts(self, target_username: str = None) -> Optional[Dict]:
        """Scrape posts where the user is tagged (either people or locations)"""
        try:
            # If no specific username provided, use the users.txt list
            if not target_username:
                users_file = "assets/users.txt"
                if not os.path.exists(users_file):
                    console.print(f"[red]Users file not found: {users_file}[/red]")
                    return None
                
                with open(users_file, "r", encoding="utf-8") as f:
                    target_usernames = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                
                if not target_usernames:
                    console.print("[yellow]No valid usernames found in users.txt[/yellow]")
                    return None
                
                results = {}
                for username in target_usernames:
                    result = self._scrape_single_user_tagged_posts(username)
                    if result:
                        results[username] = result
                return results
            else:
                return self._scrape_single_user_tagged_posts(target_username)
            
        except Exception as e:
            console.print(f"[red]Tagged posts scraping failed: {e}[/red]")
            return None

    def _scrape_single_user_tagged_posts(self, username: str) -> Optional[Dict]:
        """Helper method to scrape tagged posts for a single user"""
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Scraping tagged posts for {username}[/yellow]")
            
            output_dir = os.path.join("scraped_data", username)
            os.makedirs(output_dir, exist_ok=True)
            
            uid = self._safe_request(self.client.user_id_from_username, username)
            if not uid:
                return None
                
            # Scrape user tagged posts (where user is tagged in photos)
            user_tagged = self._safe_request(self.client.usertag_medias, user_id=uid, amount=50)
            
            # Prepare data structure
            tagged_data = {
                "username": username,
                "user_id": str(uid),
                "tagged_posts": [],
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "scraped_by": self.username
            }
            
            if user_tagged:
                for post in user_tagged:
                    try:
                        post_data = {
                            "post_id": str(post.id),
                            "post_url": f"https://www.instagram.com/p/{post.code}/",
                            "post_type": str(post.media_type),
                            "caption": str(post.caption_text) if post.caption_text else "",
                            "like_count": int(post.like_count) if hasattr(post, 'like_count') else 0,
                            "comment_count": int(post.comment_count) if hasattr(post, 'comment_count') else 0,
                            "owner_username": str(post.user.username) if hasattr(post.user, 'username') else "",
                            "owner_id": str(post.user.pk) if hasattr(post.user, 'pk') else "",
                            "taken_at": str(post.taken_at) if hasattr(post, 'taken_at') else ""
                        }
                        tagged_data["tagged_posts"].append(post_data)
                    except Exception as e:
                        if self.config.debug:
                            console.print(f"[yellow]Error processing post {post.id}: {e}[/yellow]")
                        continue
            
            # Save to JSON file
            json_file = os.path.join(output_dir, f"{username}_tagged_posts.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(tagged_data, f, indent=4, ensure_ascii=False)
            
            # Save to simple text file
            txt_file = os.path.join(output_dir, f"{username}_taggedposts.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(f"Tagged Posts for {username}\n")
                f.write(f"Scraped at: {tagged_data['scraped_at']}\n")
                f.write(f"Total tagged posts found: {len(tagged_data['tagged_posts'])}\n\n")
                
                for post in tagged_data["tagged_posts"]:
                    f.write(f"Post ID: {post['post_id']}\n")
                    f.write(f"URL: {post['post_url']}\n")
                    f.write(f"Type: {post['post_type']}\n")
                    f.write(f"Posted by: @{post['owner_username']}\n")
                    f.write(f"Likes: {post['like_count']}\n")
                    f.write(f"Comments: {post['comment_count']}\n")
                    f.write(f"Caption: {post['caption']}\n")
                    f.write(f"Posted at: {post['taken_at']}\n")
                    f.write("-" * 50 + "\n\n")
            
            console.print(f"[green]Saved tagged posts data for {username} to {txt_file}[/green]")
            return tagged_data
            
        except Exception as e:
            console.print(f"[red]Error scraping tagged posts for {username}: {e}[/red]")
            return None

    def interact_with_highlight(self, target_username: str, mode: str = "random"):
        """Interact with user's highlights (like and view)"""
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Interacting with highlights for {target_username}[/yellow]")
                
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                return
                
            highlights = self._safe_request(self.client.user_highlights, user_id=uid)
            if not highlights:
                console.print(f"[yellow]No highlights found for {target_username}[/yellow]")
                return
                
            if mode == "oldest":
                highlights.sort(key=lambda x: x.taken_at if hasattr(x, 'taken_at') else 0)
            elif mode == "latest":
                highlights.sort(key=lambda x: x.taken_at if hasattr(x, 'taken_at') else 0, reverse=True)
            else:  # random
                random.shuffle(highlights)
            
            def process_highlight(highlight):
                try:
                    # View the highlight
                    self._safe_request(self.client.highlight_seen, highlight_id=highlight.id)
                    console.print(f"[green]{self.username}: Viewed highlight {highlight.id}[/green]")
                    
                    # Like the highlight (if possible)
                    if self.can_like():
                        self._safe_request(self.client.media_like, media_id=highlight.id)
                        self.like_count_today += 1
                        console.print(f"[green]{self.username}: Liked highlight {highlight.id}[/green]")
                    
                    time.sleep(random.uniform(
                        max(1, self.config.delays["like"] - 1),
                        self.config.delays["like"] + 1
                    ))
                    
                except Exception as e:
                    console.print(f"[red]Highlight interaction error: {e}[/red]")
                    if "rate limited" in str(e).lower():
                        time.sleep(60)

            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_highlight, highlights[:3])  # Only interact with 3 highlights max
                        
        except Exception as e:
            console.print(f"[red]Highlight interaction failed: {e}[/red]")

    def scrape_profile_info(self, target_username: str) -> Optional[Dict]:
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Scraping profile info for {target_username}[/yellow]")
            
            output_dir = os.path.join("scraped_data", target_username)
            os.makedirs(output_dir, exist_ok=True)
            
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                return None
                
            info = self._safe_request(self.client.user_info, uid)
            if not info or not hasattr(info, 'pk'):
                return None
            
            # Custom JSON encoder to handle Instagram objects
            class InstagramEncoder(json.JSONEncoder):
                def default(self, obj):
                    if hasattr(obj, 'url'):  # Handle HttpUrl objects
                        return str(obj.url)
                    elif hasattr(obj, '__dict__'):  # Handle other Instagram objects
                        return obj.__dict__
                    return super().default(obj)

            followers = []
            following = []
            
            try:
                with console.status(f"[bold green]Scraping followers for {target_username}...") as status:
                    followers_data = self._safe_request(self.client.user_followers, user_id=uid)
                    if followers_data:
                        followers = [str(user.username) if hasattr(user, 'username') else str(user) for user in followers_data.values()]
                    
                    followers_file = os.path.join(output_dir, f"{target_username}_followers.txt")
                    with open(followers_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(followers))
                    
                    if self.config.debug:
                        console.print(f"[green]Saved {len(followers)} followers to {followers_file}[/green]")
            except Exception as e:
                console.print(f"[red]Error scraping followers: {e}[/red]")
                followers = []
            
            try:
                with console.status(f"[bold green]Scraping following for {target_username}...") as status:
                    following_data = self._safe_request(self.client.user_following, user_id=uid)
                    if following_data:
                        following = [str(user.username) if hasattr(user, 'username') else str(user) for user in following_data.values()]
                    
                    following_file = os.path.join(output_dir, f"{target_username}_following.txt")
                    with open(following_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(following))
                    
                    if self.config.debug:
                        console.print(f"[green]Saved {len(following)} following to {following_file}[/green]")
            except Exception as e:
                console.print(f"[red]Error scraping following: {e}[/red]")
                following = []
            
            mutual_followers = list(set(followers) & set(following))
            mutual_count = len(mutual_followers)
            
            if mutual_followers:
                try:
                    mutual_file = os.path.join(output_dir, f"{target_username}_mutual.txt")
                    with open(mutual_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(mutual_followers))
                    if self.config.debug:
                        console.print(f"[green]Saved {mutual_count} mutual followers to {mutual_file}[/green]")
                except Exception as e:
                    console.print(f"[yellow]Error saving mutual followers: {e}[/yellow]")
            
            # Get all posts or just recent based on config
            if self.config.scrape_likes_mode == 0:  # All posts
                posts = self._safe_request(self.client.user_medias, user_id=uid, amount=info.media_count)
            else:  # Recent posts only
                posts = self._safe_request(self.client.user_medias, user_id=uid, amount=5)
            
            likers = set()
            commenters = set()
            
            if posts:
                for post in posts:
                    try:
                        # Scrape likers for all posts or just recent based on config
                        if self.config.scrape_likes_mode == 0 or post == posts[0]:  # All posts or just first (most recent)
                            post_likers = self._safe_request(self.client.media_likers, media_id=getattr(post, 'id', None))
                            if post_likers:
                                likers.update([str(user.username) if hasattr(user, 'username') else str(user) for user in post_likers])
                        
                        # Always scrape commenters from all posts
                        post_comments = self._safe_request(self.client.media_comments, media_id=getattr(post, 'id', None))
                        if post_comments:
                            commenters.update([str(comment.user.username) if hasattr(comment.user, 'username') else str(comment.user) for comment in post_comments])
                        
                        time.sleep(random.uniform(1, 3))
                    except Exception as e:
                        if self.config.debug:
                            console.print(f"[yellow]Error analyzing post interactions: {e}[/yellow]")
            
            if likers:
                try:
                    likers_file = os.path.join(output_dir, f"{target_username}_likers.txt")
                    with open(likers_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(likers))
                    if self.config.debug:
                        console.print(f"[green]Saved {len(likers)} likers to {likers_file}[/green]")
                except Exception as e:
                    console.print(f"[yellow]Error saving likers: {e}[/yellow]")
            
            if commenters:
                try:
                    commenters_file = os.path.join(output_dir, f"{target_username}_commenters.txt")
                    with open(commenters_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(commenters))
                    if self.config.debug:
                        console.print(f"[green]Saved {len(commenters)} commenters to {commenters_file}[/green]")
                except Exception as e:
                    console.print(f"[yellow]Error saving commenters: {e}[/yellow]")
            
            keywords = {
                'business': ['shop', 'store', 'business', 'entrepreneur', 'brand'],
                'influencer': ['influencer', 'creator', 'blogger', 'public figure'],
                'personal': ['personal', 'life', 'memories', 'diary'],
                'contact': ['contact', 'email', 'whatsapp', 'telegram', 'dm'],
                'location': ['based in', 'from', 'location', 'city', 'country']
            }
            
            detected_keywords = {}
            bio_text = (getattr(info, 'biography', '') or "").lower()
            full_name = (getattr(info, 'full_name', '') or "").lower()
            
            for category, words in keywords.items():
                detected = []
                for word in words:
                    if word in bio_text or word in full_name:
                        detected.append(word)
                if detected:
                    detected_keywords[category] = detected
            
            # Prepare data structure with proper serialization
            profile_data = {
                "basic_info": {
                    "username": str(getattr(info, 'username', target_username)),
                    "full_name": str(getattr(info, 'full_name', '')),
                    "bio": str(getattr(info, 'biography', '')),
                    "follower_count": int(getattr(info, 'follower_count', 0)),
                    "following_count": int(getattr(info, 'following_count', 0)),
                    "post_count": int(getattr(info, 'media_count', 0)),
                    "is_private": bool(getattr(info, 'is_private', False)),
                    "is_verified": bool(getattr(info, 'is_verified', False)),
                    "profile_pic_url": str(getattr(info, 'profile_pic_url', '')) if hasattr(info, 'profile_pic_url') else None,
                    "scraped_by": str(self.username),
                    "scraped_at": str(time.strftime("%Y-%m-%d %H:%M:%S")),
                    "scraped_from": "profile"
                },
                "relationships": {
                    "followers_count": int(len(followers)),
                    "followers_sample": [str(u) for u in followers[:200]],
                    "followers_file": str(os.path.basename(followers_file)) if followers else None,
                    "following_count": int(len(following)),
                    "following_sample": [str(u) for u in following[:200]],
                    "following_file": str(os.path.basename(following_file)) if following else None,
                    "mutual_count": int(mutual_count),
                    "mutual_sample": [str(u) for u in mutual_followers[:200]],
                    "mutual_file": str(os.path.basename(mutual_file)) if mutual_followers else None
                },
                "interactions": {
                    "recent_likers": [str(u) for u in list(likers)[:200]],
                    "likers_file": str(os.path.basename(likers_file)) if likers else None,
                    "recent_commenters": [str(u) for u in list(commenters)[:200]],
                    "commenters_file": str(os.path.basename(commenters_file)) if commenters else None,
                    "interaction_score": int(len(likers) + len(commenters)),
                    "scrape_mode": "all_posts" if self.config.scrape_likes_mode == 0 else "recent_only"
                },
                "keywords": {str(k): [str(w) for w in v] for k, v in detected_keywords.items()},
                "metadata": {
                    "scraping_account": str(self.username),
                    "scraping_time": str(time.strftime("%Y-%m-%d %H:%M:%S")),
                    "scraping_source": "direct_profile",
                    "data_files": [
                        str(os.path.basename(followers_file)) if followers else None,
                        str(os.path.basename(following_file)) if following else None,
                        str(os.path.basename(mutual_file)) if mutual_followers else None,
                        str(os.path.basename(likers_file)) if likers else None,
                        str(os.path.basename(commenters_file)) if commenters else None
                    ]
                }
            }
            
            json_file = os.path.join(output_dir, f"{target_username}_data.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=4, ensure_ascii=False, cls=InstagramEncoder)
            
            console.print(f"\n[bold]Profile Info for {target_username}:[/bold]")
            console.print(f"Username: {profile_data['basic_info']['username']}")
            console.print(f"Full Name: {profile_data['basic_info']['full_name']}")
            console.print(f"Followers: {profile_data['basic_info']['follower_count']} (saved {len(followers)} to file)")
            console.print(f"Following: {profile_data['basic_info']['following_count']} (saved {len(following)} to file)")
            console.print(f"Mutual Connections: {mutual_count}")
            console.print(f"Likers Found: {len(likers)} (scrape mode: {'all posts' if self.config.scrape_likes_mode == 0 else 'recent only'})")
            console.print(f"Recent Commenters: {len(commenters)}")
            console.print(f"Posts: {profile_data['basic_info']['post_count']}")
            console.print(f"Bio: {profile_data['basic_info']['bio']}")
            console.print(f"Detected Keywords: {', '.join([f'{k}: {v}' for k, v in detected_keywords.items()])}")
            console.print(f"\n[green]All data saved to {output_dir}[/green]")
            
            return profile_data
            
        except Exception as e:
            console.print(f"[red]Profile scraping failed: {e}[/red]")
            import traceback
            traceback.print_exc()
            return None
        
    def interact_with_stories(self, usernames: List[str], like: bool = True, react: bool = False):
        """View and optionally like/react to stories of given usernames"""
        def process_story(username):
            try:
                if self.config.debug:
                    console.print(f"[yellow]{self.username}: Interacting with {username}'s stories...[/yellow]")
                    
                uid = self._safe_request(self.client.user_id_from_username, username)
                if not uid:
                    return
                    
                stories = self._safe_request(self.client.user_stories, uid)
                if not stories:
                    if self.config.debug:
                        console.print(f"[yellow]No stories found for {username}[/yellow]")
                    return
                    
                for story in stories:
                    # View the story first - using the correct parameter format
                    try:
                        # Try different parameter formats based on instagrapi version
                        if hasattr(self.client, 'story_seen'):
                            # For newer versions
                            self._safe_request(self.client.story_seen, [story.id])
                        else:
                            # Fallback to media_seen for older versions
                            self._safe_request(self.client.media_seen, [story.id])
                    
                    except Exception as e:
                        console.print(f"[yellow]Couldn't mark story as seen: {e}[/yellow]")
                        continue
                    
                    # Like the story if enabled and we haven't hit our daily limit
                    if like and self.can_like():
                        try:
                            self._safe_request(self.client.story_like, story.id)
                            self.like_count_today += 1
                            console.print(f"[green]{self.username}: Liked {username}'s story[/green]")
                        except Exception as e:
                            console.print(f"[yellow]Couldn't like story: {e}[/yellow]")
                    
                    # React to the story if enabled (using random emoji)
                    if react and self.can_comment():
                        try:
                            emojis = ["❤️", "🔥", "😍", "👏", "👍", "😊", "🤩"]
                            reaction = random.choice(emojis)
                            self._safe_request(self.client.story_react, story.id, reaction)
                            self.comment_count_today += 1
                            console.print(f"[green]{self.username}: Reacted '{reaction}' to {username}'s story[/green]")
                        except Exception as e:
                            console.print(f"[yellow]Couldn't react to story: {e}[/yellow]")
                    
                    time.sleep(random.uniform(
                        max(0.5, self.config.delays["story_view"] - 0.5),
                        self.config.delays["story_view"] + 0.5
                    ))
                    
                console.print(f"[green]{self.username}: Interacted with {username}'s stories[/green]")
                
            except Exception as e:
                console.print(f"[red]Story interaction error: {e}[/red]")

        with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            executor.map(process_story, [u.strip() for u in usernames if u.strip()])

    def scrape_location_posts(self, location_name: str, limit: int = None) -> Optional[Dict]:
        """Scrape posts from a specific location using location search"""
        try:
            if not limit:
                limit = self.config.location_posts_limit
                
            console.print(f"[yellow]Scraping location {location_name} (limit: {limit})[/yellow]")
            
            # Create location directory
            safe_location_name = "".join(c for c in location_name if c.isalnum() or c in " _-")
            location_dir = os.path.join("scraped_data", "locations", safe_location_name)
            os.makedirs(location_dir, exist_ok=True)
            
            # NEW: Correct location search with proper parameters
            try:
                # Try the most standard approach first
                location = self._safe_request(self.client.location_search, query=location_name)
            except Exception as e:
                console.print(f"[yellow]Primary location search failed, trying fallback: {str(e)}[/yellow]")
                try:
                    # Fallback to search with coordinates (default to 0,0)
                    location = self._safe_request(self.client.location_search, 
                                                lat=0.0, 
                                                lng=0.0, 
                                                query=location_name)
                except Exception as e:
                    console.print(f"[red]All location search methods failed: {str(e)}[/red]")
                    return None

            if not location:
                console.print(f"[red]No locations found for {location_name}[/red]")
                return None
                
            # Get first result's ID (handles both .pk and .id attributes)
            location_id = getattr(location[0], 'pk', getattr(location[0], 'id', None))
            if not location_id:
                console.print(f"[red]Could not extract location ID from response[/red]")
                return None
            
            # Get posts for location
            location_posts = self._safe_request(self.client.location_medias_top, 
                                            location_id=location_id, 
                                            amount=limit)
            
            if not location_posts:
                console.print(f"[yellow]No posts found for location {location_name}[/yellow]")
                return None
                
            # Process posts
            owner_usernames = []
            location_data = {
                "location_name": location_name,
                "location_id": str(location_id),
                "posts": []
            }
            
            def process_post(post):
                try:
                    if hasattr(post, 'user') and hasattr(post.user, 'username'):
                        username = post.user.username
                        owner_usernames.append(username)
                        
                        post_data = {
                            "post_id": str(post.id),
                            "post_url": f"https://www.instagram.com/p/{post.code}/",
                            "owner": username,
                            "likes": getattr(post, "like_count", 0),
                            "timestamp": str(getattr(post, "taken_at", ""))
                        }
                        location_data["posts"].append(post_data)
                except Exception as e:
                    console.print(f"[yellow]Error processing post {getattr(post, 'id', 'unknown')}: {str(e)}[/yellow]")
                    return

            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_post, location_posts)
            
            location_data["owner_usernames"] = list(set(owner_usernames))  # Remove duplicates
            
            # Save data
            json_file = os.path.join(location_dir, f"{safe_location_name}_data.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(location_data, f, indent=4, ensure_ascii=False)
            
            txt_file = os.path.join(location_dir, "mutuals.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(location_data["owner_usernames"]))
            
            console.print(f"[green]Successfully scraped {len(location_data['posts'])} posts from {location_name}[/green]")
            return location_data
            
        except Exception as e:
            console.print(f"[red]Critical error in location scraping: {str(e)}[/red]", exc_info=True)
            return None

    def scrape_user_tagged_posts(self, target_username: str) -> Optional[Dict]:
        """Scrape posts where the user is tagged and extract accounts who tagged them"""
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Scraping posts tagging {target_username}[/yellow]")
            
            output_dir = os.path.join("scraped_data", target_username)
            os.makedirs(output_dir, exist_ok=True)
            
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                return None
                
            # Get posts where the user is tagged
            tagged_posts = self._safe_request(self.client.usertag_medias, user_id=uid, amount=50)
            
            if not tagged_posts:
                console.print(f"[yellow]No posts found tagging {target_username}[/yellow]")
                return None
                
            # Extract usernames of accounts who tagged the target
            tagger_usernames = []
            tagged_data = {
                "target_username": target_username,
                "target_id": str(uid),
                "tagger_usernames": [],
                "tagged_posts": [],
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "scraped_by": self.username
            }
            
            def process_post(post):
                try:
                    if hasattr(post, 'user') and hasattr(post.user, 'username'):
                        username = post.user.username
                        if username not in tagger_usernames:
                            tagger_usernames.append(username)
                            
                        post_data = {
                            "post_id": str(post.id),
                            "post_url": f"https://www.instagram.com/p/{post.code}/",
                            "tagger_username": username,
                            "caption": str(post.caption_text) if post.caption_text else "",
                            "like_count": int(post.like_count) if hasattr(post, 'like_count') else 0,
                            "comment_count": int(post.comment_count) if hasattr(post, 'comment_count') else 0,
                            "taken_at": str(post.taken_at) if hasattr(post, 'taken_at') else ""
                        }
                        tagged_data["tagged_posts"].append(post_data)
                except Exception as e:
                    if self.config.debug:
                        console.print(f"[yellow]Error processing tagged post: {e}[/yellow]")
                    return

            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_post, tagged_posts)
            
            tagged_data["tagger_usernames"] = tagger_usernames
            
            # Save to JSON file
            json_file = os.path.join(output_dir, f"{target_username}_tagged_by.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(tagged_data, f, indent=4, ensure_ascii=False)
            
            # Save usernames to mutuals-style text file
            txt_file = os.path.join(output_dir, "mutuals.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write("\n".join(tagger_usernames))
            
            console.print(f"[green]Saved tagged posts data for {target_username} to {output_dir}[/green]")
            console.print(f"[green]Found {len(tagger_usernames)} unique accounts tagging this user[/green]")
            
            return tagged_data
            
        except Exception as e:
            console.print(f"[red]Error scraping tagged posts for {target_username}: {e}[/red]")
            return None

    def scrape_likers_commenters(self, target_username: str) -> bool:
        """Scrape all likers and commenters of a target username and save to file"""
        try:
            if self.config.debug:
                console.print(f"[yellow]{self.username}: Scraping likers and commenters for {target_username}[/yellow]")
            
            # Create output directory
            output_dir = os.path.join("scraped_data", target_username)
            os.makedirs(output_dir, exist_ok=True)
            
            # Get user ID
            uid = self._safe_request(self.client.user_id_from_username, target_username)
            if not uid:
                console.print(f"[red]Could not find user ID for {target_username}[/red]")
                return False
                
            # Get user's posts
            posts = self._safe_request(
                self.client.user_medias, 
                user_id=uid, 
                amount=self.config.max_posts_to_scrape
            )
            
            if not posts:
                console.print(f"[yellow]No posts found for {target_username}[/yellow]")
                return False
                
            # Initialize sets to store unique usernames
            likers = set()
            commenters = set()
            
            def process_post(post):
                try:
                    # Get likers
                    post_likers = self._safe_request(self.client.media_likers, media_id=post.id)
                    if post_likers:
                        likers.update(str(user.username) for user in post_likers)
                    
                    # Get commenters
                    post_comments = self._safe_request(self.client.media_comments, media_id=post.id)
                    if post_comments:
                        commenters.update(str(comment.user.username) for comment in post_comments)
                    
                    # Add delay between posts
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    if self.config.debug:
                        console.print(f"[yellow]Error processing post {post.id}: {e}[/yellow]")
                    return

            with ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
                executor.map(process_post, posts)
            
            # Combine and sort usernames
            all_users = sorted(likers.union(commenters))
            
            # Save to file
            output_file = os.path.join(output_dir, "likers_commenters.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(f"# Likers and Commenters for {target_username}\n")
                f.write(f"# Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total unique users: {len(all_users)}\n")
                f.write(f"# Total likers: {len(likers)}\n")
                f.write(f"# Total commenters: {len(commenters)}\n\n")
                f.write("\n".join(all_users))
            
            console.print(f"[green]Successfully scraped {len(all_users)} unique users for {target_username}[/green]")
            console.print(f"[green]Saved to: {output_file}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]Error scraping likers and commenters: {e}[/red]")
            return False

class IGAIO:
    def __init__(self):
        os.system("mode con: cols=100 lines=35")
        self.check_assets()
        self.accounts = self.load_accounts()
        self.proxies = self.load_proxies()
        self.sessionids = self.load_sessionids()
        self.clients = self.initialize_clients()
        
        if not self.clients:
            console.print("\n[bold red]CRITICAL: No active accounts![/bold red]")
            console.print(Markdown("""
            **Possible solutions:**
            1. Check `assets/accounts.txt` format: `username:password` or `username:password:sessionid`
            2. Verify credentials work manually
            3. Disable 2FA temporarily for testing
            4. Try without proxies first
            5. Check `login_errors.log` for details
            """))
            Prompt.ask("\nPress Enter to exit...", console=console)
            exit()

    def check_assets(self):
        os.makedirs("assets", exist_ok=True)
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("scraped_data", exist_ok=True)
        
        if not os.path.exists("assets/accounts.txt"):
            with open("assets/accounts.txt", "w") as f:
                f.write("# Format: username:password or username:password:sessionid\n")
                f.write("example1:password123\n")
                f.write("example2:password456:sessionid_here\n")
            console.print("[yellow]Created accounts.txt template[/yellow]")
        
        if not os.path.exists("assets/message.txt"):
            with open("assets/message.txt", "w", encoding="utf-8") as f:
                f.write("""Hi {name}! 👋

I noticed your profile and thought you might be interested in our new product. 
Let me know if you'd like more details!

Best regards,
Team""")
            console.print("[yellow]Created message.txt template[/yellow]")
        
        if not os.path.exists("assets/comments.txt"):
            with open("assets/comments.txt", "w", encoding="utf-8") as f:
                f.write("""Great content! 👏
Awesome post! 😊
Love this! ❤️
Nice work! 👍
Looking good! 🤩""")
            console.print("[yellow]Created comments.txt template[/yellow]")
            
        if not os.path.exists("assets/users.txt"):
            with open("assets/users.txt", "w", encoding="utf-8") as f:
                f.write("# Add target usernames here (one per line)\n")
                f.write("example_user1\n")
                f.write("example_user2\n")
            console.print("[yellow]Created users.txt template[/yellow]")
            
        if not os.path.exists("assets/completed_follows.txt"):
            open("assets/completed_follows.txt", "w").close()
            
        if not os.path.exists("assets/completed_unfollows.txt"):
            open("assets/completed_unfollows.txt", "w").close()

    def load_accounts(self):
        if not os.path.exists("assets/accounts.txt"):
            return []

        accounts = []
        with open("assets/accounts.txt", "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    parts = line.split(":", 2)  # Split into max 3 parts
                    if len(parts) >= 2:
                        username = parts[0].strip()
                        password = parts[1].strip()
                        sessionid = parts[2].strip() if len(parts) > 2 else None
                        accounts.append((username, password, sessionid))
        return accounts

    def load_proxies(self):
        if not os.path.exists("assets/proxies.txt"):
            return []

        with open("assets/proxies.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]

    def load_sessionids(self):
        if not os.path.exists("assets/sessionids.txt"):
            return []

        with open("assets/sessionids.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]

    def initialize_clients(self):
        clients = []
        console.print("\n[bold]Account Login Status:[/bold]")
        
        with Progress() as progress:
            task = progress.add_task("Logging in...", total=len(self.accounts))
            
            for i, (username, password, sessionid) in enumerate(self.accounts):
                proxy = self.proxies[i] if i < len(self.proxies) else None
                
                if sessionid:
                    # Try session ID login first
                    client = InstagramClient(username, password=None, proxy=proxy, sessionid=sessionid)
                else:
                    # Fall back to regular login
                    client = InstagramClient(username, password, proxy=proxy)
                
                if client.is_active():
                    clients.append(client)
                    progress.console.print(f"[green]{username}: Active[/green]")
                else:
                    progress.console.print(f"[red]{username}: Failed[/red]")
                
                progress.update(task, advance=1)
                time.sleep(1)
        
        return clients

    def clean_input(self, prompt, default=None):
        while True:
            result = Prompt.ask(prompt, default=default, console=console).strip()
            if result:
                return result
            console.print("[red]Input cannot be empty[/red]")

    def mass_dm(self):
        target_file = Prompt.ask(
            "Enter target file path (from scraped_data)", 
            default="scraped_data/example_user/example_user_followers.txt"
        )
        
        if not os.path.exists(target_file):
            console.print(f"[red]Target file not found: {target_file}[/red]")
            return
            
        active_client = random.choice(self.clients)
        active_client.mass_dm(target_file)

    def menu(self):
        while True:
            os.system("cls")
            console.print(Align.center(Panel(
                f"[bold magenta]IG AIO[/bold magenta]\nActive Accounts: {len(self.clients)}/{len(self.accounts)}",
                expand=False
            )))
            
            table = Table(title="Main Menu", show_header=True)
            table.add_column("Option", style="cyan", justify="center")
            table.add_column("Action", justify="left")
            table.add_row("1", "View Stories")
            table.add_row("2", "Interact with Highlights")
            table.add_row("3", "Scrape Profile Info")
            table.add_row("4", "Scrape Tagged Posts")
            table.add_row("5", "Mass DM")
            table.add_row("6", "Mass Follow/Unfollow")
            table.add_row("7", "Engagement Summary")
            table.add_row("8", "Mass Comment & Like")
            table.add_row("9", "Like Recent Posts (1-3)")
            table.add_row("10", "Interact with Stories (Like/React)")
            table.add_row("11", "Scrape Location Posts")
            table.add_row("12", "Scrape User Tagged Posts")
            table.add_row("13", "Scrape Likers & Commenters")
            table.add_row("0", "Exit")
            
            console.print(Align.center(table))
            
            choice = Prompt.ask("\n[bold cyan]Select option[/bold cyan]", 
                              choices=["0","1","2","3","4","5","6","7","8","9", "10", "11", "12", "13"], 
                              console=console)

            if choice == "1":
                usernames = self.clean_input("Usernames (comma separated)").split(",")
                # Distribute usernames across all clients
                for client in self.clients:
                    client.view_stories(usernames)
                    
            elif choice == "2":
                target = self.clean_input("Target username")
                mode = Prompt.ask("Mode (oldest/latest/random)", choices=["oldest","latest","random"], default="random")
                for client in self.clients:
                    client.interact_with_highlight(target, mode)
                    
            elif choice == "3":
                target = self.clean_input("Target username")
                # Distribute scraping across all clients
                for client in self.clients:
                    client.scrape_profile_info(target)
                    
            elif choice == "4":
                scrape_option = Prompt.ask(
                    "Scrape for (1) Specific user or (2) All users in users.txt?", 
                    choices=["1", "2"],
                    default="1"
                )
                
                if scrape_option == "1":
                    target = self.clean_input("Target username")
                    # Distribute scraping across all clients
                    for client in self.clients:
                        client.scrape_tagged_posts(target)
                else:
                    # Distribute scraping across all active clients
                    users_file = "assets/users.txt"
                    if not os.path.exists(users_file):
                        console.print(f"[red]Users file not found: {users_file}[/red]")
                        Prompt.ask("\nPress Enter to continue...", console=console)
                        continue
                    
                    with open(users_file, "r", encoding="utf-8") as f:
                        usernames = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    
                    if not usernames:
                        console.print("[yellow]No valid usernames found in users.txt[/yellow]")
                        Prompt.ask("\nPress Enter to continue...", console=console)
                        continue
                    
                    # Distribute usernames randomly across clients
                    random.shuffle(usernames)
                    random.shuffle(self.clients)
                    
                    users_per_client = max(1, len(usernames) // len(self.clients))
                    
                    with Progress() as progress:
                        task = progress.add_task("Scraping tagged posts...", total=len(usernames))
                        
                        for i, client in enumerate(self.clients):
                            start_idx = i * users_per_client
                            end_idx = start_idx + users_per_client
                            client_usernames = usernames[start_idx:end_idx]
                            
                            if not client_usernames:
                                continue
                                
                            for username in client_usernames:
                                client.scrape_tagged_posts(username)
                                progress.update(task, advance=1)
                                time.sleep(random.uniform(1, 3))
                    
            elif choice == "5":
                self.mass_dm()
                    
            elif choice == "6":
                action = Prompt.ask("Follow or Unfollow? (f/u)", choices=["f","u"], console=console)
                
                users_file = "assets/users.txt"
                if not os.path.exists(users_file):
                    console.print(f"[red]Users file not found: {users_file}[/red]")
                    Prompt.ask("\nPress Enter to continue...", console=console)
                    continue
                
                with open(users_file, "r", encoding="utf-8") as f:
                    usernames = [line.strip() for line in f if line.strip()]
                
                if not usernames:
                    console.print("[red]No usernames found in users.txt[/red]")
                    Prompt.ask("\nPress Enter to continue...", console=console)
                    continue
                
                if action == "f":
                    # Get active clients that haven't reached their following limit
                    active_clients = []
                    for client in self.clients:
                        try:
                            current_following = client._safe_request(client.client.user_info, client.client.user_id).following_count
                            if current_following < client.config.max_following_limit:
                                active_clients.append(client)
                                console.print(f"[green]{client.username}: Can follow {client.config.max_following_limit - current_following} more users[/green]")
                            else:
                                console.print(f"[yellow]{client.username}: Already at max following limit ({current_following}/{client.config.max_following_limit})[/yellow]")
                        except Exception as e:
                            console.print(f"[red]Error checking {client.username}'s following count: {e}[/red]")
                    
                    if not active_clients:
                        console.print("[red]No accounts available for following (all at max limit)[/red]")
                        Prompt.ask("\nPress Enter to continue...", console=console)
                        continue
                    
                    # Distribute usernames among active clients
                    random.shuffle(usernames)
                    random.shuffle(active_clients)
                    
                    users_per_client = max(1, len(usernames) // len(active_clients))
                    
                    with Progress() as progress:
                        task = progress.add_task("Following users...", total=len(usernames))
                        
                        for i, client in enumerate(active_clients):
                            start_idx = i * users_per_client
                            end_idx = start_idx + users_per_client
                            client_usernames = usernames[start_idx:end_idx]
                            
                            if not client_usernames:
                                continue
                                
                            client.mass_follow(client_usernames)
                            progress.update(task, advance=len(client_usernames))
                else:
                    # Existing unfollow logic
                    random.shuffle(self.clients)
                    users_per_account = max(1, len(usernames) // len(self.clients))
                    
                    for i, client in enumerate(self.clients):
                        client_usernames = usernames[i*users_per_account:(i+1)*users_per_account]
                        client.mass_unfollow(client_usernames)
                    
            elif choice == "7":
                target = self.clean_input("Target username")
                for client in self.clients:
                    client.engagement_summary(target)
                    
            elif choice == "8":
                target = self.clean_input("Target username")
                for client in self.clients:
                    client.mass_comment_like(target)
                    
            elif choice == "9":
                target = self.clean_input("Target username")
                count = int(Prompt.ask("Number of posts to like (1-3)", choices=["1","2","3"], default="3"))
                for client in self.clients:
                    client.like_recent_posts(target, count)

            elif choice == "10":
                usernames = self.clean_input("Usernames (comma separated)").split(",")
                like = Prompt.ask("Like stories? (y/n)", choices=["y","n"], default="y") == "y"
                react = Prompt.ask("React to stories? (y/n)", choices=["y","n"], default="n") == "y"
                for client in self.clients:
                    client.interact_with_stories(usernames, like=like, react=react)

            elif choice == "11":
                location = self.clean_input("Location name to scrape")
                limit = int(Prompt.ask("Number of posts to scrape", default=str(self.clients[0].config.location_posts_limit)))
                for client in self.clients:
                    client.scrape_location_posts(location, limit)

            elif choice == "12":
                target = self.clean_input("Target username to find who tagged them")
                for client in self.clients:
                    client.scrape_user_tagged_posts(target)
                    
            elif choice == "13":
                target = self.clean_input("Target username to scrape likers and commenters")
                for client in self.clients:
                    client.scrape_likers_commenters(target)
                    
            elif choice == "0":
                break
                
            Prompt.ask("\n[green]Press Enter to continue...[/green]", console=console)

if __name__ == "__main__":
    try:
        IGAIO().menu()
    except KeyboardInterrupt:
        console.print("\n[red]Program terminated by user[/red]")
    except Exception as e:
        console.print(f"\n[red]Critical error: {e}[/red]")
    finally:
        console.print("\n[blue]Goodbye![/blue]")