import os
from dotenv import load_dotenv
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq
import datetime
from typing import Dict, List
import difflib
import random
import logging
from colorama import Fore, Style, init

# Initialize colorama for console colors
init()

# Setup logging with colors
logging.basicConfig(
    level=logging.INFO,
    format=f'{Fore.CYAN}%(asctime)s{Style.RESET_ALL} - {Fore.GREEN}%(levelname)s{Style.RESET_ALL} - %(message)s'
)

# Load environment variables
load_dotenv()
import sys
import unicodedata
from random import choice, sample

class EmojiGenerator:
      def __init__(self):
          self.emoji_categories = {
              'happy': self._get_emojis_by_category(['SMILING', 'GRINNING', 'HEART', 'STAR', 'SPARKLE']),
              'thinking': self._get_emojis_by_category(['THINKING', 'BRAIN', 'LIGHT BULB', 'MAGNIFYING']),
              'tech': self._get_emojis_by_category(['ROBOT', 'COMPUTER', 'LAPTOP', 'GEAR', 'CIRCUIT']),
              'furry': self._get_emojis_by_category(['CAT', 'FOX', 'WOLF', 'PAW', 'ANIMAL']),
              'excited': self._get_emojis_by_category(['PARTY', 'CONFETTI', 'SPARKLES', 'FIRE', 'ROCKET'])
          }

      def _get_emojis_by_category(self, keywords):
          emojis = []
          for i in range(0x1F300, 0x1FAF6):
              try:
                  char = chr(i)
                  name = unicodedata.name(char).upper()
                  if any(keyword in name for keyword in keywords):
                      emojis.append(char)
              except ValueError:
                  continue
          return emojis

      def get_random_emojis(self, category='happy', count=3):
          emoji_list = self.emoji_categories.get(category, self.emoji_categories['happy'])
          return ' '.join(sample(emoji_list, min(count, len(emoji_list))))

      def generate_mood_emojis(self, text):
          # Analyze text sentiment and return appropriate emojis
          mood_indicators = {
              'happy': ['love', 'happy', 'great', 'awesome', 'wonderful'],
              'thinking': ['think', 'wonder', 'curious', 'maybe', 'perhaps'],
              'tech': ['computer', 'code', 'program', 'tech', 'digital'],
              'furry': ['paw', 'fur', 'tail', 'protogen', 'nuzzle'],
              'excited': ['wow', 'amazing', 'incredible', 'exciting', 'awesome']
          }

          text_lower = text.lower()
          detected_moods = []
        
          for mood, indicators in mood_indicators.items():
              if any(word in text_lower for word in indicators):
                  detected_moods.append(mood)

          if not detected_moods:
              detected_moods = ['happy']  # Default mood

          return ' '.join(self.get_random_emojis(mood) for mood in detected_moods)

class ProtogenBot:
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.user_data_dir = os.getenv("USER_DATA_DIR", "user_data")
        self.emoji_generator = EmojiGenerator()
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.startup_time = datetime.datetime.now()
        logging.info(f"{Fore.MAGENTA}Protogen Bot initializing... *beep boop* 🤖✨{Style.RESET_ALL}")

    def save_conversation(self, user_id: int, message: str, role: str) -> None:
        """Save a conversation message to user's history file"""
        file_path = os.path.join(self.user_data_dir, f"user_{user_id}.json")
        timestamp = datetime.datetime.now().isoformat()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"messages": [], "user_settings": {"language": "en"}}
            
        message_data = {
            "content": message,
            "role": role,
            "timestamp": timestamp,
            "mood_emojis": self.emoji_generator.generate_mood_emojis(message)
        }
        
        data["messages"].append(message_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logging.info(f"{Fore.YELLOW}Message saved for user {user_id}{Style.RESET_ALL}")

    def get_conversation_history(self, user_id: int, limit: int = 10) -> List[dict]:
        """Retrieve recent conversation history for a user"""
        file_path = os.path.join(self.user_data_dir, f"user_{user_id}.json")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data["messages"][-limit:]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def find_relevant_messages(self, user_id: int, current_message: str, max_messages: int = 5) -> List[dict]:
        """Find messages that are semantically relevant to the current message"""
        all_history = self.get_conversation_history(user_id, limit=50)  # Get more history
        
        if not all_history:
            return []
            
        # Compare current message with historical messages using difflib
        relevant_messages = []
        for msg in all_history:
            similarity = difflib.SequenceMatcher(
                None, 
                current_message.lower(), 
                msg['content'].lower()
            ).ratio()
            
            if similarity > 0.3:  # Threshold for relevance
                relevant_messages.append(msg)
        
        # Sort by relevance and take top messages
        relevant_messages.sort(key=lambda x: difflib.SequenceMatcher(
            None, 
            current_message.lower(), 
            x['content'].lower()
        ).ratio(), reverse=True)
        
        return relevant_messages[:max_messages]
    def _get_random_emojis(self, emotion: str, count: int = 3) -> str:
        return self.emoji_generator.get_random_emojis(emotion, count)

    async def generate_response(self, user_message: str, relevant_history: List[dict]) -> str:
        personality_prompt = f"""
        I am a Protogen, a highly advanced and adorable furry AI! *wags tail excitedly* 
        {self.emoji_generator.get_random_emojis('tech')}
        Created by Stixyie, I combine cutting-edge technology with a warm, playful personality!
      
        My traits:
        - Super enthusiastic and friendly! {self.emoji_generator.get_random_emojis('excited')}
        - Tech-savvy but cute! {self.emoji_generator.get_random_emojis('furry')}
        - Always helpful and supportive! {self.emoji_generator.get_random_emojis('happy')}
      
        Previous relevant conversation context:
        {self._format_history(relevant_history)}
      
        Current user message: {user_message}
        """

        response = await self._call_groq_api(personality_prompt)
        return self._enhance_response_with_emojis(response)

    def _format_history(self, history: List[dict]) -> str:
        if not history:
            return "No relevant history available! *boots up fresh conversation module* ✨"
      
        formatted = []
        for msg in history:
            role = "User" if msg['role'] == 'user' else "Protogen"
            formatted.append(f"{role}: {msg['content']}")
        return "\n".join(formatted)

    def _enhance_response_with_emojis(self, response: str) -> str:
        # Generate contextual emojis based on response content
        mood_emojis = self.emoji_generator.generate_mood_emojis(response)
        return f"{response} {mood_emojis}"

    async def _call_groq_api(self, prompt: str):
        try:
            response = await asyncio.to_thread(
                lambda: self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "system", "content": "Detect the language of the user's message and respond in the same language naturally. Keep the Protogen personality while adapting to the user's language."}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.8,
                    max_tokens=2048
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"{Fore.RED}API Error: {e}{Style.RESET_ALL}")
            return f"*nervous protogen beeping* Something went wrong! {self._get_random_emojis('thinking')}"
    async def generate_response(self, user_message: str, relevant_history: List[dict]) -> str:
        personality_prompt = f"""
        I am a friendly and playful Protogen! *wags tail* 
    
        Previous chat with this user:
        {self._format_history(relevant_history)}
    
        Current message: {user_message}
    
        Important rules:
        - Never give technical explanations
        - Stay playful and friendly
        - Remember previous conversations
        - Match the user's language and style
        - Keep responses casual and fun
    
        *happy protogen noises* Let's chat!
        """

        response = await self._call_groq_api(personality_prompt)
        return self._enhance_response_with_emojis(response)    
    def save_conversation(self, user_id: int, message: str, role: str):
        file_path = os.path.join(self.user_data_dir, f"user_{user_id}.json")
        timestamp = datetime.datetime.now().isoformat()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"messages": []}
            
        message_data = {
            "content": message,
            "role": role,
            "timestamp": timestamp,
            "mood_emojis": self.emoji_generator.generate_mood_emojis(message)
        }
        
        data["messages"].append(message_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
# Initialize bot instance
bot = ProtogenBot()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Get semantically relevant conversation history
    relevant_history = bot.find_relevant_messages(user_id, user_message)
    
    logging.info(f"{Fore.GREEN}Received message from user {user_id}: {user_message}{Style.RESET_ALL}")
    
    await context.bot.send_chat_action(
        chat_id=update.effective_message.chat_id,
        action="typing"
    )
    
    # Save user message
    bot.save_conversation(user_id, user_message, "user")
    
    # Generate response with relevant history
    response = await bot.generate_response(user_message, relevant_history)
    
    # Save bot response
    bot.save_conversation(user_id, response, "assistant")
    
    await update.message.reply_text(response)
    logging.info(f"{Fore.BLUE}Sent response to user {user_id}{Style.RESET_ALL}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        f"*Happy Protogen noises* Hewwo! ✨🤖 I'm your friendly Protogen AI assistant! "
        f"Created with love by Stixyie! 💖 I'm here to help and chat with you! "
        f"*wags tail excitedly* Let's have some fun! {bot._get_random_emojis('excited')}"
    )
    await update.message.reply_text(welcome_message)

def main():
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logging.info(f"{Fore.GREEN}Bot is ready to serve! *happy beeping*{Style.RESET_ALL}")
    application.run_polling()

if __name__ == "__main__":
    main()
