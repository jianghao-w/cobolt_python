import sys
from typing import List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTextEdit,
    QPushButton,
    QListWidget,
    QLabel,
    QComboBox,
    QSplitter,
    QMessageBox,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt
import requests

from chat_history import PersistentChatHistory
from ollama_client import OllamaClient
from ollama_worker import OllamaWorker
import uuid

class ChatWindow(QMainWindow):
    # In the ChatWindow class, modify the __init__ method:
    def __init__(self):
        super().__init__()
        self.ollama = OllamaClient()
        self.current_model = ""
        self.current_chat_id = None  # Track current chat
        self.messages = []  # Current chat messages
        self.chat_history = PersistentChatHistory()
        # Initialize UI
        self.init_ui()
        self.load_models()
        
        # Connect signals
        self.chat_history_list.itemSelectionChanged.connect(self.on_chat_selection_changed)
        
        # Load or create a new chat
        self.load_or_create_chat()
        
    def load_or_create_chat(self, chat_id: str = None):
        """Load an existing chat or create a new one"""
        try:
            if chat_id:
                # Load existing chat
                self.current_chat_id = chat_id
                messages = self.chat_history.get_messages(chat_id)
                self.messages = [
                    {"role": msg.role, "content": msg.content} for msg in messages
                ]
                
                # Update window title
                chat = self.chat_history.get_chat(chat_id)
                if chat:
                    title = chat.title or "Untitled Chat"
                    self.setWindowTitle(f"Cobolt - {title}")
            else:
                # Create new chat
                self.current_chat_id = str(uuid.uuid4())
                self.chat_history.create_chat(self.current_chat_id, "New Chat")
                self.messages = []
                self.setWindowTitle("Cobolt - New Chat")
            
            # Update chat display and history list
            self.update_chat_display()
            self.load_chat_history()  # Refresh the chat list
            return True
        except Exception as e:
            print(f"Error loading chat: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load chat: {str(e)}")
            return False
        
    def init_ui(self):
        self.setWindowTitle("Cobolt Python")
        self.setGeometry(100, 100, 1000, 700)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Left sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        
        # Model selection
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)  # Allow typing model names
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        sidebar_layout.addWidget(QLabel("Select Model:"))
        sidebar_layout.addWidget(self.model_combo)
        
        # Add a refresh models button
        refresh_btn = QPushButton("Refresh Models")
        refresh_btn.clicked.connect(self.load_models)
        sidebar_layout.addWidget(refresh_btn)
        
        # Chat history header with delete button
        history_header = QWidget()
        history_header_layout = QHBoxLayout(history_header)
        history_header_layout.setContentsMargins(0, 0, 0, 0)
        
        history_header_layout.addWidget(QLabel("Chat History:"))
        
        # Delete chat button (initially disabled)
        self.delete_chat_btn = QPushButton("-")
        self.delete_chat_btn.setFixedWidth(30)
        self.delete_chat_btn.setEnabled(False)  # Disable by default
        self.delete_chat_btn.clicked.connect(self.delete_current_chat)
        history_header_layout.addWidget(self.delete_chat_btn)
        
        history_header_layout.addStretch()
        
        sidebar_layout.addWidget(history_header)
        
        # Chat history list
        self.chat_history_list = QListWidget()
        self.chat_history_list.itemSelectionChanged.connect(self.on_chat_selection_changed)
        sidebar_layout.addWidget(self.chat_history_list)
        
        # Add new chat button
        new_chat_btn = QPushButton("New Chat")
        new_chat_btn.clicked.connect(self.new_chat)
        sidebar_layout.addWidget(new_chat_btn)
        
        # Main chat area
        chat_area = QWidget()
        chat_layout = QVBoxLayout(chat_area)
        
        # Message display
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        chat_layout.addWidget(self.message_display)
        
        # Input area
        input_area = QWidget()
        input_layout = QHBoxLayout(input_area)
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(100)
        input_layout.addWidget(self.message_input)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        
        chat_layout.addWidget(input_area)
        
        # Splitter for resizable sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar)
        splitter.addWidget(chat_area)
        splitter.setSizes([200, 600])
        
        layout.addWidget(splitter)
        
    def load_models(self):
        self.statusBar().showMessage("Loading models...")
        models = self.ollama.get_models()
        self.model_combo.clear()
        
        if not models:
            self.statusBar().showMessage("No models found. Make sure Ollama is running and models are pulled.")
            return
            
        for model in models:
            # Handle different response formats
            model_name = ""
            if isinstance(model, dict):
                model_name = model.get('name', '')
                if not model_name and 'model' in model:  # Some APIs return 'model' instead of 'name'
                    model_name = model.get('model', '')
            elif hasattr(model, 'name'):  # Handle object with name attribute
                model_name = model.name
            elif isinstance(model, str):  # Handle case where models are just strings
                model_name = model
                
            if model_name:
                self.model_combo.addItem(model_name)
        
        if self.model_combo.count() > 0:
            self.current_model = self.model_combo.currentText()
            self.statusBar().showMessage(f"Loaded {self.model_combo.count()} models")
        else:
            self.statusBar().showMessage("No valid models found in the response")
            
    def on_model_changed(self, model_name: str):
        if model_name:  # Only update if we have a valid model name
            self.current_model = model_name
            self.statusBar().showMessage(f"Model changed to: {model_name}")
        
    def new_chat(self):
        """Start a new chat, saving the current one if needed"""
        # Save the current chat if it has messages
        if hasattr(self, 'messages') and self.messages and self.current_chat_id:
            # If this was a new chat with no title yet, set a default title
            chat = self.chat_history.get_chat(self.current_chat_id)
            if chat and (not chat.title or chat.title == 'New Chat'):
                # Try to get title from first user message
                for msg in self.messages:
                    if msg.get('role') == 'user':
                        title = msg['content'][:30] + ('...' if len(msg['content']) > 30 else '')
                        self.chat_history.update_chat_title(self.current_chat_id, title)
                        break
        
        # Create a new chat
        self.current_chat_id = str(uuid.uuid4())
        self.chat_history.create_chat(self.current_chat_id, "New Chat")
        self.messages = []
        self.message_display.clear()
        self.setWindowTitle("Cobolt - New Chat")
        
        # Update the chat history list
        self.load_chat_history()
        self.statusBar().showMessage("New chat started")
        
    def send_message(self):
        if not self.current_model:
            QMessageBox.warning(self, "No Model Selected", "Please select a model first")
            return
            
        user_message = self.message_input.toPlainText().strip()
        if not user_message:
            return
        
        # Clear any previous message tracking
        if hasattr(self, '_message_saved'):
            delattr(self, '_message_saved')
            
        # If this is the first message, update the chat title
        if len(self.messages) == 0 and user_message:
            title = user_message[:30] + "..." if len(user_message) > 30 else user_message
            self.chat_history.update_chat_title(self.current_chat_id, title)
            self.setWindowTitle(f"Cobolt - {title}")
            self.load_chat_history()  # Refresh the chat list with new title
            
        # Add user message to chat
        self.messages.append({"role": "user", "content": user_message})
        self.chat_history.add_message(self.current_chat_id, "user", user_message)
        self.update_chat_display()
        self.message_input.clear()
        
        # Show "typing" indicator
        self.messages.append({"role": "assistant", "content": "Thinking..."})
        self.update_chat_display()
        
        # Start a thread for the API call
        self.worker = OllamaWorker(self.ollama, self.current_model, self.messages[:-1])  # Exclude the "Thinking..." message
        self.worker.response_received.connect(self.handle_ollama_response)
        self.worker.response_complete.connect(self.handle_complete_response)  # Connect the complete signal
        self.worker.error_occurred.connect(self.handle_ollama_error)
        self.worker.start()
        
    def handle_ollama_error(self, error_msg: str):
        """Handle errors from the Ollama worker"""
        # Remove "Thinking..." message if it exists
        if self.messages and self.messages[-1].get("content") == "Thinking...":
            self.messages.pop()
            self.update_chat_display()
        
        # Show error to user
        QMessageBox.critical(self, "Error", f"An error occurred: {error_msg}")
        self.statusBar().showMessage(f"Error: {error_msg}")
    
    def handle_ollama_response(self, response: str):
        """Handle streaming response from Ollama (UI updates only)"""
        # Remove "Thinking..." message if it exists
        if self.messages and self.messages[-1].get("content") == "Thinking...":
            self.messages.pop()
        
        # Update or add the assistant's message in memory
        if self.messages and self.messages[-1].get("role") == "assistant":
            self.messages[-1]["content"] = response
        else:
            self.messages.append({"role": "assistant", "content": response})
        
        self.update_chat_display()

    def handle_complete_response(self, response: str):
        """Handle the complete response from Ollama (saves to database)"""
        # Only save to database if we haven't already saved this message
        if self.current_chat_id and not hasattr(self, '_message_saved'):
            # Make sure we have the complete response in our messages
            if self.messages and self.messages[-1].get("role") == "assistant":
                self.messages[-1]["content"] = response
                self.update_chat_display()
            
            # Save to database
            self.chat_history.add_message(self.current_chat_id, "assistant", response)
            self._message_saved = True

    def update_window_title(self, title: str):
        """Update the window title with the chat title"""
        self.setWindowTitle(f"Cobolt Python - {title}")

    # Add a method to load chat history in the sidebar
    def load_chat_history(self):
        """Load chat history into the sidebar"""
        # Disconnect the signal to prevent triggering chat loading while updating
        try:
            self.chat_history_list.itemSelectionChanged.disconnect()
        except:
            pass
            
        self.chat_history_list.clear()
        
        chats = self.chat_history.get_recent_chats()
        for chat in chats:
            item = QListWidgetItem(chat.title or 'Untitled Chat')
            item.setData(Qt.ItemDataRole.UserRole, chat.id)
            self.chat_history_list.addItem(item)
            
            # Select the current chat if it exists in the list
            if chat.id == self.current_chat_id:
                self.chat_history_list.setCurrentItem(item)
        
        # Reconnect the signal
        self.chat_history_list.itemSelectionChanged.connect(self.on_chat_selection_changed)
    
    def on_chat_selection_changed(self):
        """Handle chat selection changes"""
        # Enable/disable delete button based on selection
        selected = self.chat_history_list.currentItem() is not None
        self.delete_chat_btn.setEnabled(selected)
        
        # Only load chat if it's not already loaded
        current_row = self.chat_history_list.currentRow()
        if current_row >= 0 and self.chat_history_list.item(current_row).data(Qt.ItemDataRole.UserRole) != self.current_chat_id:
            self.on_chat_selected(self.chat_history_list.item(current_row).data(Qt.ItemDataRole.UserRole))

    def delete_current_chat(self):
        """Delete the currently selected chat"""
        current_item = self.chat_history_list.currentItem()
        if not current_item:
            print("No chat selected for deletion")
            return
            
        chat_id = current_item.data(Qt.ItemDataRole.UserRole)
        if not chat_id:
            print("No chat ID found for selected item")
            return
            
        # Get current chat list before deletion for debugging
        current_chats = self.chat_history.get_recent_chats()
        print(f"Current number of chats before deletion: {len(current_chats)}")
        print(f"Chats before deletion: {[c.id for c in current_chats]}")
        print(f"Attempting to delete chat ID: {chat_id}")
        print(f"Current active chat ID: {self.current_chat_id}")
        
        # Find the next chat to select after deletion
        current_row = self.chat_history_list.row(current_item)
        next_chat_id = None
        
        # Determine which chat to select after deletion
        if len(current_chats) > 1:
            if current_row == len(current_chats) - 1:  # Last item
                next_chat_id = current_chats[current_row - 1].id
            else:
                next_chat_id = current_chats[current_row + 1].id
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            'Delete Chat',
            'Are you sure you want to delete this chat?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete the chat from database
                if self.chat_history.delete_chat(chat_id):
                    print(f"Successfully deleted chat {chat_id} from database")
                    
                    # Get remaining chats after deletion
                    remaining_chats = self.chat_history.get_recent_chats()
                    print(f"Number of remaining chats: {len(remaining_chats)}")
                    print(f"Remaining chat IDs: {[c.id for c in remaining_chats]}")
                    
                    # Clear and repopulate the chat history list
                    self.chat_history_list.clear()
                    self.load_chat_history()
                    
                    # Select the next chat if available
                    if next_chat_id:
                        for i in range(self.chat_history_list.count()):
                            if (
                                self.chat_history_list.item(i).data(Qt.ItemDataRole.UserRole)
                                == next_chat_id
                            ):
                                self.chat_history_list.setCurrentRow(i)
                                self.on_chat_selected(next_chat_id)
                                break
                    elif remaining_chats:
                        self.chat_history_list.setCurrentRow(0)
                        self.on_chat_selected(remaining_chats[0].id)
                    else:  # No chats left, create a new one
                        self.new_chat()
                        
            except Exception as e:
                print(f"Error deleting chat: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to delete chat: {str(e)}")
    
    def on_chat_selected(self, chat_id):
        """Handle chat selection from the sidebar"""
        if chat_id != self.current_chat_id:
            self.load_or_create_chat(chat_id)
        
    def handle_error(self, error_msg: str):
        self.statusBar().showMessage(f"Error: {error_msg}")
        # Remove "Thinking..." message if it exists
        if self.messages and self.messages[-1].get("content") == "Thinking...":
            self.messages.pop()
        self.messages.append({"role": "assistant", "content": f"Error: {error_msg}"})
        self.update_chat_display()
        
    def update_chat_display(self):
        display_text = ""
        for msg in self.messages:
            role = "You" if msg["role"] == "user" else "Assistant"
            display_text += f"<b>{role}:</b><br/>{msg['content']}<br/><br/>"
        self.message_display.setHtml(display_text)
        # Auto-scroll to bottom
        self.message_display.verticalScrollBar().setValue(
            self.message_display.verticalScrollBar().maximum()
        )

    def closeEvent(self, event):
        """Handle window close event"""
        if hasattr(self, 'current_chat_id') and self.current_chat_id:
            try:
                # Check if this is an empty chat (no messages or only system messages)
                is_empty = True
                for msg in getattr(self, 'messages', []):
                    if msg.get('role') == 'user' and msg.get('content'):
                        is_empty = False
                        break
                
                if is_empty:
                    # Delete the empty chat
                    self.chat_history.delete_chat(self.current_chat_id)
                else:
                    # Save the chat with proper title
                    current_title = self.windowTitle().replace("Cobolt - ", "")
                    if not current_title or current_title == "New Chat":
                        # Try to get title from first user message
                        for msg in self.messages:
                            if msg.get('role') == 'user' and msg.get('content'):
                                current_title = msg['content'][:30] + ("..." if len(msg['content']) > 30 else "")
                                break
                        
                        if not current_title or current_title == "New Chat":
                            current_title = "Untitled Chat"
                    
                    # Update the chat title
                    self.chat_history.update_chat_title(self.current_chat_id, current_title)
                    
            except Exception as e:
                print(f"Error handling chat on close: {e}")
        
        event.accept()


def check_ollama_running():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Check if Ollama is running
    if not check_ollama_running():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Ollama Not Running")
        msg.setInformativeText(
            "Could not connect to Ollama. Please make sure Ollama is running and accessible at http://localhost:11434\n\n"
            "You can start Ollama by running 'ollama serve' in your terminal."
        )
        msg.setWindowTitle("Connection Error")
        msg.exec()
        sys.exit(1)
    
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())