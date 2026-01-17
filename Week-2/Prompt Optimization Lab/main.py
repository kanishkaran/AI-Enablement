import os
from openai import AzureOpenAI
from dotenv import load_dotenv 

load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("OPENAI_API_VERSION")
)


class BillingChatbot:
    def __init__(self, deployment_name="gpt-4.1"):
        self.deployment_name = deployment_name
        self.conversation_history = []
        self.current_system_prompt = None
    
    def get_response(self, user_message, system_prompt):
        """Get response from Azure OpenAI with specified system prompt"""
        
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            response = client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *self.conversation_history
                ],
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message.content
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = []
    
    def save_conversation_to_readme(self):
        """Save conversation history to README file"""
        readme_content = f"""# Billing Chatbot Conversation History\n## **System Prompt Used:** {self.current_system_prompt}\n\n## Conversation\n\n"""
        for msg in self.conversation_history:
            role = msg["role"].upper()
            content = msg["content"]
            readme_content += f"### {role}\n```\n{content}\n```\n"
        
        with open(f"conversation_history_{self.current_system_prompt}.md", "w") as file:
            file.write(readme_content)
        
        print("Conversation saved to conversation_history.md")

def display_prompt_menu():
    """Display menu for selecting system prompt"""
    print("\n" + "="*50)
    print("SELECT SYSTEM PROMPT")
    print("="*50)
    print("1. Standard Prompt (improved_prompt.txt)")
    print("2. Chain-of-Thought Prompt (CoT_prompt.txt)")
    print("="*50)

def choose_system_prompt() -> str:
    """Gets user's choice on the system prompt"""
    display_prompt_menu()
    choice = input("Enter your choice (1 or 2): ").strip()
    
    while True:
        if choice == "1":
            with open("improved_prompt.txt", "r") as file:
                return file.read(), "Standard_Prompt"
        elif choice == "2":
            with open("CoT_prompt.txt", "r") as file:
                return file.read(), "Chain-of-Thought_Prompt"
        else:
            print("Invalid choice. Please enter 1 or 2.")

def main():
    chatbot = BillingChatbot()
    
    # Initial prompt selection
    system_prompt, type = choose_system_prompt()
    
    chatbot.current_system_prompt = type
    
    print("\nType 'switch' to change prompts, 'quit' to exit and save conversation.\n")
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() == "quit":
            chatbot.save_conversation_to_readme()
            print("Goodbye!")
            break
        
        elif user_input.lower() == "switch":
           chatbot.save_conversation_to_readme()
           system_prompt, type =  choose_system_prompt()
           chatbot.current_system_prompt = type
           
           chatbot.reset_conversation()
    
        elif user_input:
            response = chatbot.get_response(user_input, system_prompt)
            print(f"\nAssistant: {response}\n")
        
        else:
            print("Please enter a message or command.")
            
if __name__ == "__main__":
    main()