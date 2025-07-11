import psutil
import os
import json
from typing import List, Dict, Any, Optional, Callable
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import tempfile
import shutil
import threading
import queue
import time
from enum import Enum
from dataclasses import dataclass, asdict
import uuid 
import math
import statistics
from collections import deque
import sqlite3

# Load environment variables from .env file
load_dotenv()

# === OpenAI API Setup ===
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = "nvidia/llama-3.3-nemotron-super-49b-v1"

if not API_KEY:
    raise ValueError("API_KEY is not set in environment variables")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# === Agent Communication Protocol ===
class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    COLLABORATION = "collaboration"
    QUESTION = "question"
    FEEDBACK = "feedback"
    URGENT = "urgent"

class AgentRole(Enum):
    ANALYST = "analyst"
    DATA_SCIENTIST = "datascientist"
    UI_DESIGNER = "ui_designer"
    FRONTEND_DEV = "frontend_dev"
    BACKEND_DEV = "backend_dev"
    PROMPT_DESIGNER = "prompt_designer"
    PROMPT_ENGINEER = "prompt_engineer"
    PROMPT_ANALYST = "prompt_analyst"
    COORDINATOR = "coordinator"
    CHATBOT = "chatbot"
@dataclass
class AgentMessage:
    id: str
    sender: AgentRole
    receiver: AgentRole
    message_type: MessageType
    content: str
    context: Dict[str, Any] = None
    priority: int = 1  # 1=low, 2=medium, 3=high, 4=urgent
    timestamp: str = None
    requires_response: bool = False
    response_timeout: int = 30  # seconds
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.context is None:
            self.context = {}



# === Enhanced Agent Communication Hub ===
class EnhancedAgentCommunicationHub:
    def __init__(self, file_manager):
        self.file_manager = file_manager
        self.agent_queues = {role: queue.Queue() for role in AgentRole}
        self.agent_files = {}
        self.communication_log = []
        self.active_agents = set()
        self.message_history = []
        self.collaboration_sessions = {}
        self.waiting_responses = {}
        self.hub_running = True
        
        # Start the communication hub thread
        self.hub_thread = threading.Thread(target=self._hub_worker, daemon=True)
        self.hub_thread.start()
    
    def _hub_worker(self):
        """Background worker to handle inter-agent communication"""
        while self.hub_running:
            try:
                # Process any pending messages
                self._process_pending_messages()
                # Clean up expired response waits
                self._cleanup_expired_waits()
                time.sleep(0.1)  # Small delay to prevent busy waiting
            except Exception as e:
                print(f"❌ Hub worker error: {e}")
    
    def _process_pending_messages(self):
        """Process messages in agent queues"""
        for role, msg_queue in self.agent_queues.items():
            if not msg_queue.empty():
                try:
                    message = msg_queue.get_nowait()
                    self._route_message(message)
                except queue.Empty:
                    continue
    
    def _route_message(self, message: AgentMessage):
        """Route message to appropriate handler"""
        self.message_history.append(message)
        self.log_communication(
            message.sender.value, 
            f"→ {message.receiver.value}: {message.message_type.value}",
            message.content[:100]
        )
        
        # If this is a response to a waiting request
        if message.message_type == MessageType.RESPONSE:
            response_key = f"{message.receiver.value}_{message.sender.value}"
            if response_key in self.waiting_responses:
                self.waiting_responses[response_key]['response'] = message
                self.waiting_responses[response_key]['received'] = True
    
    def _cleanup_expired_waits(self):
        """Clean up expired response waits"""
        current_time = time.time()
        expired_keys = []
        
        for key, wait_info in self.waiting_responses.items():
            if not wait_info['received'] and current_time - wait_info['start_time'] > wait_info['timeout']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.waiting_responses[key]
    
    def register_agent(self, agent_role: AgentRole):
        """Register an agent as active"""
        self.active_agents.add(agent_role)
        self.log_communication(agent_role.value, "Agent registered and active")
    
    def send_message(self, message: AgentMessage):
        """Send a message from one agent to another"""
        if message.receiver not in self.active_agents:
            print(f"⚠️ Agent {message.receiver.value} is not active")
            return False
        
        self.agent_queues[message.receiver].put(message)
        
        # If response is required, set up waiting mechanism
        if message.requires_response:
            wait_key = f"{message.sender.value}_{message.receiver.value}"
            self.waiting_responses[wait_key] = {
                'start_time': time.time(),
                'timeout': message.response_timeout,
                'received': False,
                'response': None
            }
        
        return True
    
    def wait_for_response(self, sender: AgentRole, receiver: AgentRole, timeout: int = 30) -> Optional[AgentMessage]:
        """Wait for a response from another agent"""
        wait_key = f"{sender.value}_{receiver.value}"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if wait_key in self.waiting_responses and self.waiting_responses[wait_key]['received']:
                response = self.waiting_responses[wait_key]['response']
                del self.waiting_responses[wait_key]
                return response
            time.sleep(0.1)
        
        return None
    
    def broadcast_message(self, sender: AgentRole, content: str, message_type: MessageType = MessageType.NOTIFICATION):
        """Broadcast a message to all active agents"""
        for agent_role in self.active_agents:
            if agent_role != sender:
                message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender=sender,
                    receiver=agent_role,
                    message_type=message_type,
                    content=content
                )
                self.send_message(message)
    
    def request_collaboration(self, sender: AgentRole, receivers: List[AgentRole], topic: str, context: Dict = None) -> str:
        """Request collaboration with multiple agents"""
        session_id = str(uuid.uuid4())
        self.collaboration_sessions[session_id] = {
            'initiator': sender,
            'participants': receivers,
            'topic': topic,
            'context': context or {},
            'messages': [],
            'start_time': datetime.now().isoformat()
        }
        
        # Send collaboration invitations
        for receiver in receivers:
            message = AgentMessage(
                id=str(uuid.uuid4()),
                sender=sender,
                receiver=receiver,
                message_type=MessageType.COLLABORATION,
                content=f"Collaboration request: {topic}",
                context={'session_id': session_id, 'topic': topic, 'context': context}
            )
            self.send_message(message)
        
        return session_id
    
    def get_messages_for_agent(self, agent_role: AgentRole) -> List[AgentMessage]:
        """Get all pending messages for an agent"""
        messages = []
        while not self.agent_queues[agent_role].empty():
            try:
                message = self.agent_queues[agent_role].get_nowait()
                messages.append(message)
            except queue.Empty:
                break
        return messages
    
    def log_communication(self, agent: str, action: str, data: Any = None):
        """Log inter-agent communication"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "action": action,
            "data_summary": str(data)[:200] if data else None
        }
        self.communication_log.append(log_entry)
        print(f"📋 [{agent}] {action}")
    
    def save_agent_work(self, agent: str, data: Dict, phase: str = "") -> str:
        """Save agent work to file and track it"""
        filepath = self.file_manager.save_agent_data(agent, data, phase)
        self.agent_files[agent] = filepath
        self.log_communication(agent, f"Saved work to file: {os.path.basename(filepath)}")
        return filepath
    
    def load_agent_work(self, agent: str) -> Dict:
        """Load agent work from file"""
        if agent in self.agent_files:
            filepath = self.agent_files[agent]
        else:
            filepath = self.file_manager.get_latest_agent_file(agent)
        
        if filepath and os.path.exists(filepath):
            data = self.file_manager.load_agent_data(filepath)
            self.log_communication(agent, f"Loaded work from file: {os.path.basename(filepath)}")
            return data
        else:
            print(f"⚠️ No saved work found for agent: {agent}")
            return {}
    
    def get_collaboration_context(self, session_id: str) -> Dict:
        """Get collaboration session context"""
        return self.collaboration_sessions.get(session_id, {})
    
    def shutdown(self):
        """Shutdown the communication hub"""
        self.hub_running = False
        if self.hub_thread.is_alive():
            self.hub_thread.join(timeout=5)

# === Enhanced Agent Base Class ===
class EnhancedAgent:
    def __init__(self, role: AgentRole, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        self.role = role
        self.communication_hub = communication_hub
        self.chatbot_config = chatbot_config
        self.is_active = False
        self.collaboration_sessions = {}
        self.context_memory = {}
        
        # Message queue and help request stubs
        self.message_queue = []
        self.help_requests = []
        self.collaborative_sessions = []
        
        # Register with communication hub
        self.communication_hub.register_agent(self.role)
        self.is_active = True
    
    def send_message(self, receiver: AgentRole, content: str, message_type: MessageType = MessageType.REQUEST, 
                    requires_response: bool = False, context: Dict = None, priority: int = 1):
        """Send a message to another agent"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=self.role,
            receiver=receiver,
            message_type=message_type,
            content=content,
            context=context or {},
            priority=priority,
            requires_response=requires_response
        )
        return self.communication_hub.send_message(message)
    
    def ask_for_help(self, helper_agent: AgentRole, question: str, context: Dict = None) -> Optional[str]:
        """Ask another agent for help and wait for response"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=self.role,
            receiver=helper_agent,
            message_type=MessageType.QUESTION,
            content=question,
            context=context or {},
            requires_response=True,
            priority=2
        )
        
        if self.communication_hub.send_message(message):
            response = self.communication_hub.wait_for_response(self.role, helper_agent)
            return response.content if response else None
        return None
    
    def request_collaboration(self, agents: List[AgentRole], topic: str, context: Dict = None) -> str:
        """Request collaboration with multiple agents"""
        return self.communication_hub.request_collaboration(self.role, agents, topic, context)
    
    def process_incoming_messages(self):
        """Process incoming messages"""
        messages = self.communication_hub.get_messages_for_agent(self.role)
        
        for message in messages:
            self._handle_message(message)
    
    def _handle_message(self, message: AgentMessage):
        """Handle incoming message"""
        if message.message_type == MessageType.QUESTION:
            response_content = self._handle_question(message.content, message.context)
            if response_content:
                self.send_response(message.sender, response_content, message.id)
        
        elif message.message_type == MessageType.COLLABORATION:
            session_id = message.context.get('session_id')
            if session_id:
                self._join_collaboration(session_id, message.context)
        
        elif message.message_type == MessageType.FEEDBACK:
            self._handle_feedback(message.content, message.context)
    
    def send_response(self, receiver: AgentRole, content: str, original_message_id: str):
        """Send a response to another agent"""
        message = AgentMessage(
            id=str(uuid.uuid4()),
            sender=self.role,
            receiver=receiver,
            message_type=MessageType.RESPONSE,
            content=content,
            context={'original_message_id': original_message_id}
        )
        self.communication_hub.send_message(message)
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents - to be implemented by subclasses"""
        return f"I'm {self.role.value} and I received your question: {question}"
    
    def _join_collaboration(self, session_id: str, context: Dict):
        """Join a collaboration session"""
        self.collaboration_sessions[session_id] = context
        print(f"🤝 [{self.role.value}] Joined collaboration session: {session_id}")
    
    def _handle_feedback(self, feedback: str, context: Dict):
        """Handle feedback from other agents"""
        print(f"📝 [{self.role.value}] Received feedback: {feedback[:100]}...")
    
    def call_AI(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1000, context: Dict = None) -> str:
        """Call AI with role-specific context"""
        try:
            # Add agent-specific context
            role_context = self._get_role_context()
            if context:
                role_context.update(context)
            
            context_str = f"\n\nContext: {json.dumps(role_context, indent=2)}" if role_context else ""
            full_prompt = f"{self._get_role_prompt()}{context_str}\n\n{prompt}"
            
            print(f"📡 [{self.role.value}] Calling AI...")
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": full_prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ [{self.role.value}] AI call failed: {e}")
            return ""
    
    def _get_role_prompt(self) -> str:
        """Get role-specific prompt - to be implemented by subclasses"""
        return f"You are a {self.role.value} working on a chatbot project."
    
    def _get_role_context(self) -> Dict:
        """Get role-specific context"""
        return {
            "role": self.role.value,
            "chatbot_config": self.chatbot_config,
            "active_collaborations": list(self.collaboration_sessions.keys())
        }

# === Specialized Agent Classes ===
class AnalystAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.ANALYST, communication_hub, chatbot_config)
        self.analysis_cache = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a professional Data Analyst with expertise in content analysis, user behavior, and website optimization. 
        You can collaborate with other agents and provide insights based on your analysis."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "content analysis" in question.lower():
            return self._provide_content_analysis_help(question, context)
        elif "user behavior" in question.lower():
            return self._provide_user_behavior_help(question, context)
        elif "insights" in question.lower():
            return self._provide_insights_help(question, context)
        else:
            return f"As an analyst, I can help with content analysis, user behavior patterns, and insights. Your question: {question}"
    
    def _provide_content_analysis_help(self, question: str, context: Dict) -> str:
        """Provide content analysis assistance"""
        analysis_prompt = f"""
        As a data analyst, provide insights for this question about content analysis:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        Chatbot Type: {self.chatbot_config.get('type', 'general')}
        
        Focus on actionable insights for content optimization.
        """
        return self.call_AI(analysis_prompt, temperature=0.3)
    
    def _provide_user_behavior_help(self, question: str, context: Dict) -> str:
        """Provide user behavior analysis"""
        behavior_prompt = f"""
        Analyze user behavior patterns for this question:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        Chatbot Type: {self.chatbot_config.get('type', 'general')}
        
        Provide insights on user intent, journey, and interaction patterns.
        """
        return self.call_AI(behavior_prompt, temperature=0.4)
    
    def _provide_insights_help(self, question: str, context: Dict) -> str:
        """Provide general insights"""
        insights_prompt = f"""
        Provide strategic insights for this question:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on data-driven recommendations and strategic implications.
        """
        return self.call_AI(insights_prompt, temperature=0.3)
    
    def analyze_content_with_collaboration(self, content_lines: List[str]) -> Dict:
        """Analyze content with potential collaboration"""
        self.process_incoming_messages()
        
        # Ask data scientist for preprocessing suggestions
        preprocessing_help = self.ask_for_help(
            AgentRole.DATA_SCIENTIST,
            "What preprocessing steps should I consider for this content analysis?",
            {"content_sample": content_lines[:5], "chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Perform analysis
        analysis_prompt = f"""
        Analyze content for {self.chatbot_config.get('type', 'general')} chatbot:
        
        Preprocessing recommendations: {preprocessing_help}
        Content sample: {content_lines[:10]}
        
        Provide comprehensive analysis focusing on:
        1. Content quality and relevance
        2. User intent patterns
        3. Chatbot optimization opportunities
        4. Collaboration needs with other agents
        """
        
        analysis = self.call_AI(analysis_prompt, temperature=0.3)
        
        # Share insights with relevant agents
        self.send_message(
            AgentRole.DATA_SCIENTIST,
            f"Content analysis complete. Key findings: {analysis[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_analysis": analysis}
        )
        
        return {
            "analysis": analysis,
            "preprocessing_suggestions": preprocessing_help,
            "collaboration_insights": "Shared findings with data scientist"
        }

class DataScientistAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.DATA_SCIENTIST, communication_hub, chatbot_config)
        self.models_cache = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a senior Data Scientist specializing in NLP, content clustering, and user intent analysis. 
        You collaborate with analysts and developers to optimize data processing and model performance."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "preprocessing" in question.lower():
            return self._provide_preprocessing_help(question, context)
        elif "clustering" in question.lower():
            return self._provide_clustering_help(question, context)
        elif "modeling" in question.lower():
            return self._provide_modeling_help(question, context)
        else:
            return f"As a data scientist, I can help with preprocessing, clustering, modeling, and NLP tasks. Your question: {question}"
    
    def _provide_preprocessing_help(self, question: str, context: Dict) -> str:
        """Provide preprocessing assistance"""
        preprocessing_prompt = f"""
        As a data scientist, recommend preprocessing steps for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Provide specific, actionable preprocessing recommendations.
        """
        return self.call_AI(preprocessing_prompt, temperature=0.3)
    
    def _provide_clustering_help(self, question: str, context: Dict) -> str:
        """Provide clustering assistance"""
        clustering_prompt = f"""
        Recommend clustering approaches for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Suggest appropriate clustering algorithms and parameters.
        """
        return self.call_AI(clustering_prompt, temperature=0.4)
    
    def _provide_modeling_help(self, question: str, context: Dict) -> str:
        """Provide modeling assistance"""
        modeling_prompt = f"""
        Provide modeling recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Suggest appropriate models and evaluation metrics.
        """
        return self.call_AI(modeling_prompt, temperature=0.3)
    
    def process_content_with_collaboration(self, content_lines: List[str]) -> Dict:
        """Process content with collaboration"""
        self.process_incoming_messages()
        
        # Ask analyst for content insights
        analyst_insights = self.ask_for_help(
            AgentRole.ANALYST,
            "What are the key content patterns I should focus on for clustering?",
            {"content_sample": content_lines[:5]}
        )
        
        # Ask UI designer about user interaction patterns
        ui_insights = self.ask_for_help(
            AgentRole.UI_DESIGNER,
            "What user interaction patterns should influence my content processing?",
            {"chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Process content with insights
        processing_prompt = f"""
        Process content based on collaborative insights:
        
        Analyst insights: {analyst_insights}
        UI insights: {ui_insights}
        Content sample: {content_lines[:10]}
        
        Provide:
        1. Content clustering strategy
        2. Intent classification approach
        3. Knowledge graph structure
        4. Q&A generation strategy
        """
        
        processing = self.call_AI(processing_prompt, temperature=0.4)
        
        # Share results with relevant agents
        self.send_message(
            AgentRole.PROMPT_DESIGNER,
            f"Content processing complete. Q&A strategy: {processing[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_processing": processing}
        )
        
        return {
            "processing": processing,
            "analyst_insights": analyst_insights,
            "ui_insights": ui_insights,
            "collaborative_approach": "Integrated insights from analyst and UI designer"
        }

class UIDesignerAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.UI_DESIGNER, communication_hub, chatbot_config)
        self.design_patterns = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a modern UI/UX designer with expertise in conversational interfaces and user experience optimization. 
        You collaborate with developers and analysts to create optimal user experiences."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "user interaction" in question.lower():
            return self._provide_interaction_help(question, context)
        elif "design pattern" in question.lower():
            return self._provide_design_pattern_help(question, context)
        elif "user experience" in question.lower():
            return self._provide_ux_help(question, context)
        else:
            return f"As a UI designer, I can help with user interactions, design patterns, and UX optimization. Your question: {question}"
    
    def _provide_interaction_help(self, question: str, context: Dict) -> str:
        """Provide user interaction guidance"""
        interaction_prompt = f"""
        As a UI designer, provide user interaction recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on user behavior patterns and optimal interaction flows.
        """
        return self.call_AI(interaction_prompt, temperature=0.6)
    
    def _provide_design_pattern_help(self, question: str, context: Dict) -> str:
        """Provide design pattern guidance"""
        pattern_prompt = f"""
        Recommend design patterns for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Suggest appropriate UI patterns and components.
        """
        return self.call_AI(pattern_prompt, temperature=0.6)
    
    def _provide_ux_help(self, question: str, context: Dict) -> str:
        """Provide UX guidance"""
        ux_prompt = f"""
        Provide UX recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on user experience optimization and usability.
        """
        return self.call_AI(ux_prompt, temperature=0.6)
    
    def design_ui_with_collaboration(self, qa_data: List[Dict]) -> Dict:
        """Design UI with collaboration"""
        self.process_incoming_messages()
        
        # Ask analyst for user behavior insights
        behavior_insights = self.ask_for_help(
            AgentRole.ANALYST,
            "What user behavior patterns should influence my UI design?",
            {"qa_sample": qa_data[:3], "chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Ask frontend developer about technical constraints
        tech_constraints = self.ask_for_help(
            AgentRole.FRONTEND_DEV,
            "What technical constraints should I consider for the UI design?",
            {"chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Design UI with insights
        design_prompt = f"""
        Design UI based on collaborative insights:
        
        Behavior insights: {behavior_insights}
        Technical constraints: {tech_constraints}
        Q&A data sample: {qa_data[:3] if qa_data else "None"}
        
        Create a comprehensive UI design that:
        1. Optimizes for user behavior patterns
        2. Respects technical constraints
        3. Supports the chatbot functionality
        4. Provides excellent user experience
        """
        
        design = self.call_AI(design_prompt, temperature=0.6)
        
        # Share design with developers
        self.send_message(
            AgentRole.FRONTEND_DEV,
            f"UI design complete. Key features: {design[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_design": design}
        )
        
        return {
            "design": design,
            "behavior_insights": behavior_insights,
            "tech_constraints": tech_constraints,
            "collaborative_design": "Integrated insights from analyst and frontend developer"
        }

class FrontendDevAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.FRONTEND_DEV, communication_hub, chatbot_config)
        self.frontend_specs = {}

    def _get_role_prompt(self) -> str:
        return """You are a Frontend Developer with expertise in building responsive, accessible, and performant web UIs for chatbots.
        You collaborate with UI designers and backend developers to deliver seamless user experiences."""

    def _handle_question(self, question: str, context: Dict) -> str:
        if "ui" in question.lower() or "design" in question.lower():
            return self._provide_ui_help(question, context)
        elif "api" in question.lower():
            return self._provide_api_help(question, context)
        elif "integration" in question.lower():
            return self._provide_integration_help(question, context)
        else:
            return f"As a frontend developer, I can help with UI, API integration, and frontend architecture. Your question: {question}"

    def _provide_ui_help(self, question: str, context: Dict) -> str:
        ui_prompt = f"""
        As a frontend developer, provide UI implementation recommendations for:

        Question: {question}
        Context: {json.dumps(context, indent=2)}

        Focus on usability, accessibility, and responsiveness.
        """
        return self.call_AI(ui_prompt, temperature=0.3)

    def _provide_api_help(self, question: str, context: Dict) -> str:
        api_prompt = f"""
        Provide API integration guidance for:

        Question: {question}
        Context: {json.dumps(context, indent=2)}

        Focus on data flow, error handling, and performance.
        """
        return self.call_AI(api_prompt, temperature=0.2)

    def _provide_integration_help(self, question: str, context: Dict) -> str:
        integration_prompt = f"""
        Recommend frontend-backend integration strategies for:

        Question: {question}
        Context: {json.dumps(context, indent=2)}

        Focus on maintainability and scalability.
        """
        return self.call_AI(integration_prompt, temperature=0.2)

    def develop_frontend_with_collaboration(self, ui_design: Dict, qa_data: List[Dict]) -> Dict:
        """Develop frontend with collaboration"""
        self.process_incoming_messages()

        # Ask UI designer for clarification on design details
        design_clarification = self.ask_for_help(
            AgentRole.UI_DESIGNER,
            "Can you clarify the interaction flows and responsive design requirements?",
            {"ui_design": ui_design, "chatbot_type": self.chatbot_config.get('type')}
        )

        # Ask backend developer about API requirements
        api_requirements = self.ask_for_help(
            AgentRole.BACKEND_DEV,
            "What API endpoints and data formats should I expect for the chatbot?",
            {"chatbot_type": self.chatbot_config.get('type')}
        )

        # Develop frontend with insights
        development_prompt = f"""
        Develop frontend implementation based on collaborative insights:

        UI Design: {ui_design}
        Design Clarification: {design_clarification}
        API Requirements: {api_requirements}
        Q&A Data Sample: {qa_data[:3] if qa_data else "None"}

        Create a complete frontend implementation that:
        1. Implements the UI design faithfully
        2. Handles responsive design requirements
        3. Integrates with backend APIs
        4. Provides smooth user interactions
        5. Includes error handling and loading states

        Provide HTML, CSS, and JavaScript code.
        """

        implementation = self.call_AI(development_prompt, temperature=0.3)

        # Share implementation with backend developer
        self.send_message(
            AgentRole.BACKEND_DEV,
            f"Frontend implementation complete. API integration points: {implementation[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_implementation": implementation}
        )

        return {
            "implementation": implementation,
            "design_clarification": design_clarification,
            "api_requirements": api_requirements,
            "collaborative_development": "Integrated insights from UI designer and backend developer"
        }
class BackendDevAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.BACKEND_DEV, communication_hub, chatbot_config)
        self.api_specs = {}
    
    def _get_role_prompt(self) -> str:
        return """You are an experienced Backend Developer with expertise in API development, database design, and chatbot logic. 
        You collaborate with frontend developers and data scientists to create robust backend systems."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "api" in question.lower():
            return self._provide_api_help(question, context)
        elif "database" in question.lower():
            return self._provide_database_help(question, context)
        elif "integration" in question.lower():
            return self._provide_integration_help(question, context)
        else:
            return f"As a backend developer, I can help with APIs, database design, and system integration. Your question: {question}"
    
    def _provide_api_help(self, question: str, context: Dict) -> str:
        """Provide API development guidance"""
        api_prompt = f"""
        As a backend developer, provide API recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on API design, endpoints, and data formats.
        """
        return self.call_AI(api_prompt, temperature=0.2)
    
    def _provide_database_help(self, question: str, context: Dict) -> str:
        """Provide database design guidance"""
        db_prompt = f"""
        Provide database design recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Suggest appropriate database schema and optimization strategies.
        """
        return self.call_AI(db_prompt, temperature=0.3)
    
    def _provide_integration_help(self, question: str, context: Dict) -> str:
        """Provide system integration guidance"""
        integration_prompt = f"""
        Recommend integration approaches for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on system architecture and integration patterns.
        """
        return self.call_AI(integration_prompt, temperature=0.3)
    
    def develop_backend_with_collaboration(self, processed_data: Dict, ui_requirements: Dict) -> Dict:
        """Develop backend with collaboration"""
        self.process_incoming_messages()
        
        # Ask data scientist about data processing requirements
        data_requirements = self.ask_for_help(
            AgentRole.DATA_SCIENTIST,
            "What data processing and storage requirements should I consider for the backend?",
            {"processed_data": processed_data, "chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Ask frontend developer about integration needs
        frontend_needs = self.ask_for_help(
            AgentRole.FRONTEND_DEV,
            "What specific API endpoints and response formats do you need?",
            {"ui_requirements": ui_requirements}
        )
        
        # Develop backend with insights
        backend_prompt = f"""
        Develop backend implementation based on collaborative insights:
        
        Processed Data: {processed_data}
        UI Requirements: {ui_requirements}
        Data Requirements: {data_requirements}
        Frontend Needs: {frontend_needs}
        
        Create a complete backend implementation that:
        1. Handles data storage and retrieval
        2. Provides necessary API endpoints
        3. Implements chatbot logic
        4. Supports scalability and performance
        5. Includes error handling and logging
        
        Provide API specifications and implementation details.
        """
        
        backend = self.call_AI(backend_prompt, temperature=0.3)
        
        # Share backend specs with frontend developer
        self.send_message(
            AgentRole.FRONTEND_DEV,
            f"Backend implementation complete. API endpoints: {backend[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_backend": backend}
        )
        
        return {
            "backend": backend,
            "data_requirements": data_requirements,
            "frontend_needs": frontend_needs,
            "collaborative_backend": "Integrated requirements from data scientist and frontend developer"
        }

class PromptDesignerAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.PROMPT_DESIGNER, communication_hub, chatbot_config)
        self.prompt_templates = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a specialized Prompt Designer with expertise in creating effective prompts for chatbots and AI systems. 
        You collaborate with engineers and analysts to optimize prompt performance."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "prompt" in question.lower():
            return self._provide_prompt_help(question, context)
        elif "template" in question.lower():
            return self._provide_template_help(question, context)
        elif "optimization" in question.lower():
            return self._provide_optimization_help(question, context)
        else:
            return f"As a prompt designer, I can help with prompt creation, templates, and optimization. Your question: {question}"
    
    def _provide_prompt_help(self, question: str, context: Dict) -> str:
        """Provide prompt design guidance"""
        prompt_help = f"""
        As a prompt designer, provide prompt recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on prompt effectiveness and user engagement.
        """
        return self.call_AI(prompt_help, temperature=0.4)
    
    def _provide_template_help(self, question: str, context: Dict) -> str:
        """Provide template design guidance"""
        template_help = f"""
        Provide prompt template recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Suggest reusable prompt templates and patterns.
        """
        return self.call_AI(template_help, temperature=0.4)
    
    def _provide_optimization_help(self, question: str, context: Dict) -> str:
        """Provide prompt optimization guidance"""
        optimization_help = f"""
        Recommend prompt optimization strategies for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on performance improvement and user satisfaction.
        """
        return self.call_AI(optimization_help, temperature=0.3)
    
    def design_prompts_with_collaboration(self, qa_data: List[Dict], user_insights: Dict) -> Dict:
        """Design prompts with collaboration"""
        self.process_incoming_messages()
        
        # Ask analyst for user behavior insights
        behavior_insights = self.ask_for_help(
            AgentRole.ANALYST,
            "What user behavior patterns should influence my prompt design?",
            {"qa_data": qa_data[:3], "user_insights": user_insights}
        )
        
        # Ask prompt engineer for technical requirements
        technical_requirements = self.ask_for_help(
            AgentRole.PROMPT_ENGINEER,
            "What technical considerations should I include in prompt design?",
            {"chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Design prompts with insights
        design_prompt = f"""
        Design comprehensive prompts based on collaborative insights:
        
        Q&A Data: {qa_data[:5] if qa_data else "None"}
        User Insights: {user_insights}
        Behavior Insights: {behavior_insights}
        Technical Requirements: {technical_requirements}
        
        Create a complete prompt design that:
        1. Addresses user behavior patterns
        2. Meets technical requirements
        3. Optimizes for user engagement
        4. Provides consistent responses
        5. Handles edge cases effectively
        
        Include base prompts, conversation flows, and error handling prompts.
        """
        
        prompt_design = self.call_AI(design_prompt, temperature=0.4)
        
        # Share design with prompt engineer
        self.send_message(
            AgentRole.PROMPT_ENGINEER,
            f"Prompt design complete. Key features: {prompt_design[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_prompt_design": prompt_design}
        )
        
        return {
            "prompt_design": prompt_design,
            "behavior_insights": behavior_insights,
            "technical_requirements": technical_requirements,
            "collaborative_prompts": "Integrated insights from analyst and prompt engineer"
        }

class PromptEngineerAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.PROMPT_ENGINEER, communication_hub, chatbot_config)
        self.engineering_specs = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a Prompt Engineer with expertise in implementing and optimizing prompts for production systems. 
        You collaborate with designers and analysts to ensure prompt effectiveness and performance."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "technical" in question.lower():
            return self._provide_technical_help(question, context)
        elif "implementation" in question.lower():
            return self._provide_implementation_help(question, context)
        elif "performance" in question.lower():
            return self._provide_performance_help(question, context)
        else:
            return f"As a prompt engineer, I can help with technical implementation, performance optimization, and prompt engineering. Your question: {question}"
    
    def _provide_technical_help(self, question: str, context: Dict) -> str:
        """Provide technical implementation guidance"""
        technical_help = f"""
        As a prompt engineer, provide technical recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on technical implementation and system integration.
        """
        return self.call_AI(technical_help, temperature=0.2)
    
    def _provide_implementation_help(self, question: str, context: Dict) -> str:
        """Provide implementation guidance"""
        implementation_help = f"""
        Provide implementation recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on practical implementation approaches and best practices.
        """
        return self.call_AI(implementation_help, temperature=0.3)
    
    def _provide_performance_help(self, question: str, context: Dict) -> str:
        """Provide performance optimization guidance"""
        performance_help = f"""
        Recommend performance optimizations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on prompt performance and system efficiency.
        """
        return self.call_AI(performance_help, temperature=0.2)
    
    def implement_prompts_with_collaboration(self, prompt_design: Dict, system_requirements: Dict) -> Dict:
        """Implement prompts with collaboration"""
        self.process_incoming_messages()
        
        # Ask prompt analyst for optimization suggestions
        optimization_suggestions = self.ask_for_help(
            AgentRole.PROMPT_ANALYST,
            "What optimization strategies should I apply to these prompts?",
            {"prompt_design": prompt_design, "system_requirements": system_requirements}
        )
        
        # Ask backend developer about integration requirements
        integration_requirements = self.ask_for_help(
            AgentRole.BACKEND_DEV,
            "What integration considerations should I include in prompt implementation?",
            {"chatbot_type": self.chatbot_config.get('type')}
        )
        
        # Implement prompts with insights
        implementation_prompt = f"""
        Implement prompts based on collaborative insights:
        
        Prompt Design: {prompt_design}
        System Requirements: {system_requirements}
        Optimization Suggestions: {optimization_suggestions}
        Integration Requirements: {integration_requirements}
        
        Create a complete prompt implementation that:
        1. Implements the design specifications
        2. Applies optimization strategies
        3. Meets integration requirements
        4. Includes monitoring and testing
        5. Provides documentation and maintenance guidelines
        
        Include implementation code and configuration.
        """
        
        implementation = self.call_AI(implementation_prompt, temperature=0.3)
        
        # Share implementation with prompt analyst
        self.send_message(
            AgentRole.PROMPT_ANALYST,
            f"Prompt implementation complete. Optimization applied: {implementation[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_implementation": implementation}
        )
        
        return {
            "implementation": implementation,
            "optimization_suggestions": optimization_suggestions,
            "integration_requirements": integration_requirements,
            "collaborative_implementation": "Integrated insights from prompt analyst and backend developer"
        }

class PromptAnalystAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.PROMPT_ANALYST, communication_hub, chatbot_config)
        self.analysis_results = {}
    
    def _get_role_prompt(self) -> str:
        return """You are a Prompt Analyst with expertise in evaluating prompt performance and user satisfaction. 
        You collaborate with engineers and designers to continuously improve prompt effectiveness."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "optimization" in question.lower():
            return self._provide_optimization_help(question, context)
        elif "analysis" in question.lower():
            return self._provide_analysis_help(question, context)
        elif "performance" in question.lower():
            return self._provide_performance_help(question, context)
        else:
            return f"As a prompt analyst, I can help with optimization strategies, performance analysis, and prompt evaluation. Your question: {question}"
    
    def _provide_optimization_help(self, question: str, context: Dict) -> str:
        """Provide optimization guidance"""
        optimization_help = f"""
        As a prompt analyst, provide optimization recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on data-driven optimization strategies.
        """
        return self.call_AI(optimization_help, temperature=0.3)
    
    def _provide_analysis_help(self, question: str, context: Dict) -> str:
        """Provide analysis guidance"""
        analysis_help = f"""
        Provide analysis recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on comprehensive prompt evaluation methods.
        """
        return self.call_AI(analysis_help, temperature=0.3)
    
    def _provide_performance_help(self, question: str, context: Dict) -> str:
        """Provide performance analysis guidance"""
        performance_help = f"""
        Recommend performance analysis approaches for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on measurable performance metrics and improvements.
        """
        return self.call_AI(performance_help, temperature=0.2)
    
    def analyze_prompts_with_collaboration(self, implementation: Dict, user_feedback: Dict) -> Dict:
        """Analyze prompts with collaboration"""
        self.process_incoming_messages()
        
        # Ask data scientist for analysis methodology
        analysis_methodology = self.ask_for_help(
            AgentRole.DATA_SCIENTIST,
            "What analysis methodology should I use for prompt performance evaluation?",
            {"implementation": implementation, "user_feedback": user_feedback}
        )
        
        # Ask prompt designer for design intent
        design_intent = self.ask_for_help(
            AgentRole.PROMPT_DESIGNER,
            "What was the original design intent for these prompts?",
            {"implementation": implementation}
        )
        
        # Analyze prompts with insights
        analysis_prompt = f"""
        Analyze prompt performance based on collaborative insights:
        
        Implementation: {implementation}
        User Feedback: {user_feedback}
        Analysis Methodology: {analysis_methodology}
        Design Intent: {design_intent}
        
        Provide comprehensive analysis including:
        1. Performance metrics evaluation
        2. User satisfaction analysis
        3. Alignment with design intent
        4. Optimization recommendations
        5. Future improvement strategies
        
        Include quantitative and qualitative insights.
        """
        
        analysis = self.call_AI(analysis_prompt, temperature=0.3)
        
        # Share analysis with relevant agents
        self.send_message(
            AgentRole.PROMPT_DESIGNER,
            f"Prompt analysis complete. Key insights: {analysis[:200]}...",
            MessageType.NOTIFICATION,
            context={"full_analysis": analysis}
        )
        
        return {
            "analysis": analysis,
            "analysis_methodology": analysis_methodology,
            "design_intent": design_intent,
            "collaborative_analysis": "Integrated insights from data scientist and prompt designer"
        }

class CoordinatorAgent(EnhancedAgent):
    def __init__(self, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(AgentRole.COORDINATOR, communication_hub, chatbot_config)
        self.project_status = {}
        self.workflow_steps = []
    
    def _get_role_prompt(self) -> str:
        return """You are a Project Coordinator with expertise in managing multi-agent workflows and ensuring project success. 
        You orchestrate collaboration between all agents and monitor project progress."""
    
    def _handle_question(self, question: str, context: Dict) -> str:
        """Handle questions from other agents"""
        if "workflow" in question.lower():
            return self._provide_workflow_help(question, context)
        elif "coordination" in question.lower():
            return self._provide_coordination_help(question, context)
        elif "status" in question.lower():
            return self._provide_status_help(question, context)
        else:
            return f"As a coordinator, I can help with workflow management, coordination, and project status. Your question: {question}"
    
    def _provide_workflow_help(self, question: str, context: Dict) -> str:
        """Provide workflow guidance"""
        workflow_help = f"""
        As a coordinator, provide workflow recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on efficient workflow coordination and management.
        """
        return self.call_AI(workflow_help, temperature=0.2)
    
    def _provide_coordination_help(self, question: str, context: Dict) -> str:
        """Provide coordination guidance"""
        coordination_help = f"""
        Provide coordination recommendations for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        
        Focus on effective team coordination and communication.
        """
        return self.call_AI(coordination_help, temperature=0.3)
    
    def _provide_status_help(self, question: str, context: Dict) -> str:
        """Provide project status information"""
        status_help = f"""
        Provide project status information for:
        
        Question: {question}
        Context: {json.dumps(context, indent=2)}
        Project Status: {self.project_status}
        
        Focus on current progress and next steps.
        """
        return self.call_AI(status_help, temperature=0.1)
    
    def orchestrate_project(self, content_lines: List[str]) -> Dict:
        """Orchestrate the entire project workflow"""
        self.process_incoming_messages()
        
        print("🎯 Starting coordinated chatbot development project...")
        
        # Initialize project status
        self.project_status = {
            "phase": "initialization",
            "completed_steps": [],
            "active_agents": list(self.communication_hub.active_agents),
            "start_time": datetime.now().isoformat()
        }
        
        # Phase 1: Content Analysis and Processing
        print("\n📊 Phase 1: Content Analysis and Processing")
        self.project_status["phase"] = "content_analysis"
        
        # Request collaboration for content analysis
        analysis_session = self.request_collaboration(
            [AgentRole.ANALYST, AgentRole.DATA_SCIENTIST],
            "Content Analysis and Processing",
            {"content_lines": content_lines[:10], "chatbot_config": self.chatbot_config}
        )
        
        # Wait for analysis completion (simulate)
        time.sleep(1)
        
        # Phase 2: UI/UX Design
        print("\n🎨 Phase 2: UI/UX Design")
        self.project_status["phase"] = "ui_design"
        
        # Request UI design collaboration
        design_session = self.request_collaboration(
            [AgentRole.UI_DESIGNER, AgentRole.FRONTEND_DEV],
            "UI/UX Design and Frontend Planning",
            {"content_processed": True, "chatbot_config": self.chatbot_config}
        )
        
        # Phase 3: Backend Development
        print("\n⚙️ Phase 3: Backend Development")
        self.project_status["phase"] = "backend_development"
        
        # Request backend development collaboration
        backend_session = self.request_collaboration(
            [AgentRole.BACKEND_DEV, AgentRole.DATA_SCIENTIST],
            "Backend Development and Data Integration",
            {"ui_designed": True, "chatbot_config": self.chatbot_config}
        )
        
        # Phase 4: Prompt Engineering
        print("\n🔧 Phase 4: Prompt Engineering")
        self.project_status["phase"] = "prompt_engineering"
        
        # Request prompt engineering collaboration
        prompt_session = self.request_collaboration(
            [AgentRole.PROMPT_DESIGNER, AgentRole.PROMPT_ENGINEER, AgentRole.PROMPT_ANALYST],
            "Prompt Design and Implementation",
            {"backend_ready": True, "chatbot_config": self.chatbot_config}
        )
        
        # Phase 5: Integration and Testing
        print("\n🔗 Phase 5: Integration and Testing")
        self.project_status["phase"] = "integration"
        
        # Request full integration collaboration
        integration_session = self.request_collaboration(
            [AgentRole.FRONTEND_DEV, AgentRole.BACKEND_DEV, AgentRole.PROMPT_ENGINEER],
            "System Integration and Testing",
            {"all_components_ready": True, "chatbot_config": self.chatbot_config}
        )
        
        # Phase 6: Final Analysis and Optimization
        print("\n📈 Phase 6: Final Analysis and Optimization")
        self.project_status["phase"] = "optimization"
        
        # Request final analysis collaboration
        final_session = self.request_collaboration(
            [AgentRole.ANALYST, AgentRole.PROMPT_ANALYST],
            "Final Analysis and Optimization",
            {"system_integrated": True, "chatbot_config": self.chatbot_config}
        )
        
        # Complete project
        self.project_status["phase"] = "completed"
        self.project_status["completion_time"] = datetime.now().isoformat()
        
        print("\n✅ Project coordination complete!")
        
        return {
            "project_status": self.project_status,
            "collaboration_sessions": [
                analysis_session, design_session, backend_session,
                prompt_session, integration_session, final_session
            ],
            "coordinated_workflow": "Successfully orchestrated multi-agent chatbot development"
        }

# --- Add this stub for WorkflowManager ---
class WorkflowManager:
    def __init__(self, system):
        self.system = system
        self.workflows = {}
        self.execution_history = []

    def get_predefined_workflows(self):
        return {
            "quick_analysis": {
                "steps": [
                    {"type": "analysis", "agents": ["analyst", "datascientist"]}
                ]
            }
        }

    def create_custom_workflow(self, name, steps):
        workflow_id = f"workflow_{len(self.workflows)+1}"
        self.workflows[workflow_id] = {"name": name, "steps": steps}
        return workflow_id

    def execute_workflow(self, workflow_id, content_lines):
        self.execution_history.append(workflow_id)
        return {"status": "completed", "workflow_id": workflow_id, "result": "Workflow executed"}

# === Enhanced Performance Monitor ===
class PerformanceMetric(Enum):
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_IO = "network_io"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"

class PerformanceStats:
    def __init__(self):
        self.metrics = {metric: 0.0 for metric in PerformanceMetric}
        self.sample_count = 0
    
    def update(self, new_data: Dict[PerformanceMetric, float]):
        """Update stats with new data"""
        for metric, value in new_data.items():
            if metric in self.metrics:
                self.metrics[metric] += value
        self.sample_count += 1
    
    def average(self) -> Dict[PerformanceMetric, float]:
        """Calculate average values for metrics"""
        if self.sample_count == 0:
            return {metric: 0.0 for metric in self.metrics}
        
        return {metric: value / self.sample_count for metric, value in self.metrics.items()}

class EnhancedPerformanceMonitor:
    """Enhanced performance monitoring with comprehensive tracking and analytics"""
    
    def __init__(self, max_history: int = 1000, enable_system_monitoring: bool = True):
        self.max_history = max_history
        self.enable_system_monitoring = enable_system_monitoring
        
        # Core tracking
        self.current_metrics: Dict[str, PerformanceMetric] = {}
        self.completed_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.global_stats: Dict[str, PerformanceStats] = {}
        
        # System monitoring
        self.system_snapshots: deque = deque(maxlen=max_history)
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        # Event tracking
        self.event_log: deque = deque(maxlen=max_history)
        self.thresholds: Dict[str, float] = {}
        self.alerts: List[Dict] = []
        
        # Custom metrics
        self.custom_counters: Dict[str, int] = defaultdict(int)
        self.custom_gauges: Dict[str, float] = {}
        self.custom_histograms: Dict[str, List[float]] = defaultdict(list)
        
        # Hooks and callbacks
        self.start_hooks: List[Callable] = []
        self.end_hooks: List[Callable] = []
        self.threshold_callbacks: Dict[str, Callable] = {}
        
        # Start system monitoring if enabled
        if self.enable_system_monitoring:
            self.start_system_monitoring()
    
    def start_monitoring(self, key: str, metadata: Optional[Dict] = None) -> str:
        """Start monitoring a process with enhanced tracking"""
        current_time = time.time()
        
        # Get system metrics if enabled
        memory_usage = None
        cpu_usage = None
        if self.enable_system_monitoring:
            try:
                process = psutil.Process()
                memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                cpu_usage = process.cpu_percent()
            except:
                pass
        
        # Create performance metric
        metric = PerformanceMetric(
            name=key,
            start_time=current_time,
            metadata=metadata or {},
            memory_start=memory_usage,
            cpu_start=cpu_usage
        )
        
        self.current_metrics[key] = metric
        
        # Log event
        self.log_event("start", key, {"timestamp": current_time, "metadata": metadata})
        
        # Execute start hooks
        for hook in self.start_hooks:
            try:
                hook(key, metric)
            except Exception as e:
                self.log_event("error", f"start_hook_{key}", {"error": str(e)})
        
        return key
    
    def end_monitoring(self, key: str, metadata: Optional[Dict] = None) -> Optional[PerformanceMetric]:
        """End monitoring a process and calculate metrics"""
        if key not in self.current_metrics:
            self.log_event("warning", f"end_monitoring_{key}", {"message": "Key not found in current metrics"})
            return None
        
        current_time = time.time()
        metric = self.current_metrics[key]
        
        # Update metric
        metric.end_time = current_time
        metric.duration = current_time - metric.start_time
        metric.status = "completed"
        
        # Add any additional metadata
        if metadata:
            metric.metadata.update(metadata)
        
        # Get system metrics if enabled
        if self.enable_system_monitoring:
            try:
                process = psutil.Process()
                metric.memory_end = process.memory_info().rss / 1024 / 1024  # MB
                metric.cpu_end = process.cpu_percent()
            except:
                pass
        
        # Move to completed metrics
        self.completed_metrics[key].append(metric)
        del self.current_metrics[key]
        
        # Update statistics
        self.update_stats(key)
        
        # Check thresholds
        self.check_thresholds(key, metric)
        
        # Log event
        self.log_event("end", key, {
            "timestamp": current_time,
            "duration": metric.duration,
            "metadata": metadata
        })
        
        # Execute end hooks
        for hook in self.end_hooks:
            try:
                hook(key, metric)
            except Exception as e:
                self.log_event("error", f"end_hook_{key}", {"error": str(e)})
        
        return metric
    
    def update_stats(self, key: str):
        """Update statistical analysis for a metric"""
        if key not in self.completed_metrics:
            return
        
        durations = [m.duration for m in self.completed_metrics[key] if m.duration is not None]
        if not durations:
            return
        
        stats = PerformanceStats(
            count=len(durations),
            total_time=sum(durations),
            min_time=min(durations),
            max_time=max(durations),
            avg_time=statistics.mean(durations),
            median_time=statistics.median(durations)
        )
        
        if len(durations) > 1:
            stats.std_dev = statistics.stdev(durations)
            stats.percentile_95 = statistics.quantiles(durations, n=20)[18]  # 95th percentile
            stats.percentile_99 = statistics.quantiles(durations, n=100)[98]  # 99th percentile
        
        self.global_stats[key] = stats
    
    def start_system_monitoring(self, interval: float = 1.0):
        """Start continuous system monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._system_monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
    
    def stop_system_monitoring(self):
        """Stop continuous system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
    
    def _system_monitoring_loop(self, interval: float):
        """System monitoring loop (runs in separate thread)"""
        while self.monitoring_active:
            try:
                snapshot = {
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_available": psutil.virtual_memory().available / 1024 / 1024,  # MB
                    "disk_usage": psutil.disk_usage('/').percent,
                    "active_processes": len(psutil.pids()),
                    "current_metrics_count": len(self.current_metrics)
                }
                
                # Add network I/O if available
                try:
                    net_io = psutil.net_io_counters()
                    snapshot["network_bytes_sent"] = net_io.bytes_sent
                    snapshot["network_bytes_recv"] = net_io.bytes_recv
                except:
                    pass
                
                self.system_snapshots.append(snapshot)
                
            except Exception as e:
                self.log_event("error", "system_monitoring", {"error": str(e)})
            
            time.sleep(interval)
    
    def set_threshold(self, key: str, threshold: float, callback: Optional[Callable] = None):
        """Set performance threshold with optional callback"""
        self.thresholds[key] = threshold
        if callback:
            self.threshold_callbacks[key] = callback
    
    def check_thresholds(self, key: str, metric: PerformanceMetric):
        """Check if metric exceeds threshold"""
        if key in self.thresholds and metric.duration:
            if metric.duration > self.thresholds[key]:
                alert = {
                    "timestamp": time.time(),
                    "key": key,
                    "duration": metric.duration,
                    "threshold": self.thresholds[key],
                    "severity": "warning"
                }
                self.alerts.append(alert)
                self.log_event("threshold_exceeded", key, alert)
                
                # Execute threshold callback if available
                if key in self.threshold_callbacks:
                    try:
                        self.threshold_callbacks[key](key, metric, alert)
                    except Exception as e:
                        self.log_event("error", f"threshold_callback_{key}", {"error": str(e)})
    
    def increment_counter(self, key: str, value: int = 1):
        """Increment a custom counter"""
        self.custom_counters[key] += value
        self.log_event("counter_increment", key, {"value": value, "total": self.custom_counters[key]})
    
    def set_gauge(self, key: str, value: float):
        """Set a custom gauge value"""
        self.custom_gauges[key] = value
        self.log_event("gauge_set", key, {"value": value})
    
    def record_histogram(self, key: str, value: float):
        """Record a value in a custom histogram"""
        self.custom_histograms[key].append(value)
        # Keep only recent values
        if len(self.custom_histograms[key]) > self.max_history:
            self.custom_histograms[key] = self.custom_histograms[key][-self.max_history:]
        self.log_event("histogram_record", key, {"value": value})
    
    def log_event(self, event_type: str, key: str, data: Dict):
        """Log an event"""
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "key": key,
            "data": data
        }
        self.event_log.append(event)
    
    def add_start_hook(self, hook: Callable):
        """Add a hook to execute when monitoring starts"""
        self.start_hooks.append(hook)
    
    def add_end_hook(self, hook: Callable):
        """Add a hook to execute when monitoring ends"""
        self.end_hooks.append(hook)
    
    def get_performance_report(self) -> Dict:
        """Get comprehensive performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_completed_metrics": sum(len(metrics) for metrics in self.completed_metrics.values()),
                "active_metrics": len(self.current_metrics),
                "unique_metric_types": len(self.completed_metrics),
                "total_alerts": len(self.alerts),
                "monitoring_duration": time.time() - min(
                    [m.start_time for m in self.current_metrics.values()] + 
                    [m.start_time for metrics in self.completed_metrics.values() for m in metrics]
                ) if (self.current_metrics or self.completed_metrics) else 0
            },
            "statistics": {key: self._stats_to_dict(stats) for key, stats in self.global_stats.items()},
            "current_metrics": {key: self._metric_to_dict(metric) for key, metric in self.current_metrics.items()},
            "custom_metrics": {
                "counters": dict(self.custom_counters),
                "gauges": dict(self.custom_gauges),
                "histograms": {key: self._histogram_stats(values) for key, values in self.custom_histograms.items()}
            },
            "system_metrics": self._get_system_metrics(),
            "alerts": self.alerts[-10:],  # Last 10 alerts
            "thresholds": dict(self.thresholds)
        }
        
        return report
    
    def get_detailed_report(self, key: str) -> Dict:
        """Get detailed report for a specific metric"""
        if key not in self.completed_metrics:
            return {"error": f"No data found for key: {key}"}
        
        metrics = list(self.completed_metrics[key])
        if not metrics:
            return {"error": f"No completed metrics found for key: {key}"}
        
        return {
            "key": key,
            "total_executions": len(metrics),
            "statistics": self._stats_to_dict(self.global_stats.get(key, PerformanceStats())),
            "recent_executions": [self._metric_to_dict(m) for m in metrics[-10:]],
            "performance_trend": self._calculate_trend(metrics),
            "memory_analysis": self._analyze_memory_usage(metrics),
            "timing_distribution": self._analyze_timing_distribution(metrics)
        }
    
    def export_data(self, filepath: str, format: str = "json"):
        """Export performance data to file"""
        data = self.get_performance_report()
        
        if format.lower() == "json":
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        elif format.lower() == "csv":
            import csv
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Key", "Count", "Avg Time", "Min Time", "Max Time", "Total Time"])
                for key, stats in self.global_stats.items():
                    writer.writerow([key, stats.count, stats.avg_time, stats.min_time, stats.max_time, stats.total_time])
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def clear_data(self, key: Optional[str] = None):
        """Clear performance data"""
        if key:
            if key in self.completed_metrics:
                del self.completed_metrics[key]
            if key in self.global_stats:
                del self.global_stats[key]
            if key in self.current_metrics:
                del self.current_metrics[key]
        else:
            self.completed_metrics.clear()
            self.global_stats.clear()
            self.current_metrics.clear()
            self.alerts.clear()
            self.custom_counters.clear()
            self.custom_gauges.clear()
            self.custom_histograms.clear()
    
    def _stats_to_dict(self, stats: PerformanceStats) -> Dict:
        """Convert PerformanceStats to dictionary"""
        return {
            "count": stats.count,
            "total_time": stats.total_time,
            "min_time": stats.min_time,
            "max_time": stats.max_time,
            "avg_time": stats.avg_time,
            "median_time": stats.median_time,
            "std_dev": stats.std_dev,
            "percentile_95": stats.percentile_95,
            "percentile_99": stats.percentile_99
        }
    
    def _metric_to_dict(self, metric: PerformanceMetric) -> Dict:
        """Convert PerformanceMetric to dictionary"""
        return {
            "name": metric.name,
            "start_time": metric.start_time,
            "end_time": metric.end_time,
            "duration": metric.duration,
            "status": metric.status,
            "metadata": metric.metadata,
            "memory_start": metric.memory_start,
            "memory_end": metric.memory_end,
            "cpu_start": metric.cpu_start,
            "cpu_end": metric.cpu_end
        }
    
    def _histogram_stats(self, values: List[float]) -> Dict:
        """Calculate histogram statistics"""
        if not values:
            return {}
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0
        }
    
    def _get_system_metrics(self) -> Dict:
        """Get current system metrics"""
        if not self.system_snapshots:
            return {}
        
        latest = self.system_snapshots[-1]
        return {
            "current": latest,
            "history_size": len(self.system_snapshots),
            "monitoring_active": self.monitoring_active
        }
    
    def _calculate_trend(self, metrics: List[PerformanceMetric]) -> Dict:
        """Calculate performance trend"""
        if len(metrics) < 2:
            return {"trend": "insufficient_data"}
        
        durations = [m.duration for m in metrics if m.duration is not None]
        if len(durations) < 2:
            return {"trend": "insufficient_data"}
        n = len(durations)
        x = list(range(n))
        y = durations
        
        slope = (n * sum(x[i] * y[i] for i in range(n)) - sum(x) * sum(y)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2)
        
        return {
            "trend": "improving" if slope < 0 else "degrading" if slope > 0 else "stable",
            "slope": slope,
            "recent_avg": statistics.mean(durations[-5:]) if len(durations) >= 5 else statistics.mean(durations),
            "overall_avg": statistics.mean(durations)
        }
    
    def _analyze_memory_usage(self, metrics: List[PerformanceMetric]) -> Dict:
        """Analyze memory usage patterns"""
        memory_data = [(m.memory_start, m.memory_end) for m in metrics if m.memory_start and m.memory_end]
        if not memory_data:
            return {"available": False}
        
        memory_changes = [end - start for start, end in memory_data]
        
        return {
            "available": True,
            "avg_memory_change": statistics.mean(memory_changes),
            "max_memory_increase": max(memory_changes),
            "max_memory_decrease": min(memory_changes),
            "memory_leak_suspected": statistics.mean(memory_changes) > 1.0  # > 1MB average increase
        }
    
    def _analyze_timing_distribution(self, metrics: List[PerformanceMetric]) -> Dict:
        """Analyze timing distribution"""
        durations = [m.duration for m in metrics if m.duration is not None]
        if not durations:
            return {}
        
        # Create timing buckets
        min_time = min(durations)
        max_time = max(durations)
        bucket_size = (max_time - min_time) / 10 if max_time > min_time else 0.1
        
        buckets = {}
        for duration in durations:
            bucket = int((duration - min_time) / bucket_size) if bucket_size > 0 else 0
            buckets[bucket] = buckets.get(bucket, 0) + 1
        
        return {
            "buckets": buckets,
            "bucket_size": bucket_size,
            "min_time": min_time,
            "max_time": max_time,
            "outliers": [d for d in durations if d > (statistics.mean(durations) + 2 * statistics.stdev(durations))] if len(durations) > 1 else []
        }
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop_system_monitoring()

# Context manager for easy monitoring
class PerformanceContext:
    """Context manager for performance monitoring"""

    def __init__(self):
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.system_snapshots: List[Dict] = []
        self.thresholds: Dict[str, float] = {}
        self.threshold_callbacks: Dict[str, Callable] = {}
        self.alerts: List[Dict] = []
        self.current_metrics: Dict[str, PerformanceMetric] = {}

    def __enter__(self):
        self.start_system_monitoring()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop_system_monitoring()

    def start_system_monitoring(self, interval: float = 2.0):
        """Start continuous system monitoring"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._system_monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()

    def stop_system_monitoring(self):
        """Stop continuous system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)

    def _system_monitoring_loop(self, interval: float):
        """System monitoring loop (runs in separate thread)"""
        while self.monitoring_active:
            try:
                snapshot = {
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "memory_available_MB": psutil.virtual_memory().available / 1024 / 1024,
                    "disk_usage_percent": psutil.disk_usage('/').percent,
                    "active_processes": len(psutil.pids()),
                    "current_metrics_count": len(self.current_metrics)
                }

                try:
                    net_io = psutil.net_io_counters()
                    snapshot["network_bytes_sent"] = net_io.bytes_sent
                    snapshot["network_bytes_recv"] = net_io.bytes_recv
                except:
                    pass

                self.system_snapshots.append(snapshot)

            except Exception as e:
                self.log_event("error", "system_monitoring", {"error": str(e)})

            time.sleep(interval)

    def set_threshold(self, key: str, threshold: float, callback: Optional[Callable] = None):
        """Set performance threshold with optional callback"""
        self.thresholds[key] = threshold
        if callback:
            self.threshold_callbacks[key] = callback

    def check_thresholds(self, key: str, metric: PerformanceMetric):
        """Check if metric exceeds threshold"""
        if key in self.thresholds and metric.duration:
            if metric.duration > self.thresholds[key]:
                alert = {
                    "timestamp": time.time(),
                    "key": key,
                    "duration": metric.duration,
                    "threshold": self.thresholds[key],
                    "severity": "warning"
                }
                self.alerts.append(alert)
                self.log_event("threshold_exceeded", key, alert)

                if key in self.threshold_callbacks:
                    try:
                        self.threshold_callbacks[key](key, metric, alert)
                    except Exception as e:
                        self.log_event("error", f"threshold_callback_{key}", {"error": str(e)})

    def log_event(self, event_type: str, source: str, data: dict):
        """Log an event"""
        print(f"[{datetime.now().isoformat()}] {event_type.upper()} - {source}: {data}")

    def get_performance_report(self) -> dict:
        """Get comprehensive performance report"""
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_snapshots": len(self.system_snapshots),
                "alerts_triggered": len(self.alerts),
                "monitored_keys": list(self.thresholds.keys())
            },
            "snapshots": self.system_snapshots,
            "alerts": self.alerts
        }


# Context manager for easy monitoring
class PerformanceContext:
    """Context manager for performance monitoring"""
    
    def __init__(self, monitor: EnhancedPerformanceMonitor, key: str, metadata: Optional[Dict] = None):
        self.monitor = monitor
        self.key = key
        self.metadata = metadata
        self.metric = None
    
    def __enter__(self):
        self.monitor.start_monitoring(self.key, self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.metric = self.monitor.end_monitoring(self.key)
        return False

# Decorator for function monitoring
def monitor_performance(monitor: EnhancedPerformanceMonitor, key: Optional[str] = None, metadata: Optional[Dict] = None):
    """Decorator for monitoring function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor_key = key or f"{func.__module__}.{func.__name__}"
            with PerformanceContext(monitor, monitor_key, metadata):
                return func(*args, **kwargs)
        return wrapper
    return decorator

class ChatbotAgentAPP(EnhancedAgent):
    """
    Generic Chatbot Agent for multi-agent collaboration.
    Inherit this class for custom chatbot agent roles.
    """
    def __init__(self, role: AgentRole, communication_hub: EnhancedAgentCommunicationHub, chatbot_config: Dict):
        super().__init__(role, communication_hub, chatbot_config)
        self.agent_state = {}

    def _get_role_prompt(self) -> str:
        # You can customize this prompt for your chatbot agent
        return f"You are a {self.role.value} chatbot agent. Collaborate with other agents to accomplish chatbot development tasks."

    def _handle_question(self, question: str, context: Dict) -> str:
        # Basic question handler, override for specialization
        return f"As a {self.role.value}, I received your question: {question}"

    def perform_task(self, task: str, context: Dict = None) -> str:
        """
        Perform a generic chatbot agent task.
        """
        prompt = f"Task: {task}\nContext: {json.dumps(context or {}, indent=2)}"
        return self.call_AI(prompt, temperature=0.5)

    def process_incoming_messages(self):
        """
        Optionally override to add custom message processing logic.
        """
        super().process_incoming_messages()

    def initialize(self, chatbot_config: dict):
        """Initialize or update the chatbot configuration."""
        self.chatbot_config = chatbot_config
        print(f"🤖 ChatbotAgentAPP initialized with config: {chatbot_config}")
    
    
    def run_full_development(self, content_lines):
        """Run the full chatbot development process with real agent collaboration and file operations."""
        print("Running full development process...")

        # 1. Content analysis by AnalystAgent
        analyst = AnalystAgent(self.communication_hub, self.chatbot_config)
        analysis_result = analyst.analyze_content_with_collaboration(content_lines)
        self.communication_hub.save_agent_work("analyst", analysis_result, phase="analysis")

        # 2. Data processing by DataScientistAgent
        data_scientist = DataScientistAgent(self.communication_hub, self.chatbot_config)
        processing_result = data_scientist.process_content_with_collaboration(content_lines)
        self.communication_hub.save_agent_work("datascientist", processing_result, phase="processing")

        # 3. UI design by UIDesignerAgent
        ui_designer = UIDesignerAgent(self.communication_hub, self.chatbot_config)
        ui_result = ui_designer.design_ui_with_collaboration([{"q": q, "a": "Sample answer"} for q in content_lines])
        self.communication_hub.save_agent_work("ui_designer", ui_result, phase="ui_design")

        # 4. Save overall project state
        project_state = {
            "analysis": analysis_result,
            "processing": processing_result,
            "ui_design": ui_result
        }
        self.communication_hub.save_agent_work("chatbot", project_state, phase="full_development")

        return {"success": True, "details": "Full development completed with collaboration and file operations."}

    def run_focused_development(self, content_lines, focus_area):
        """Run focused development on a specific area with collaboration."""
        print(f"Running focused development on: {focus_area}")
        result = {}
        if focus_area == "analysis":
            analyst = AnalystAgent(self.communication_hub, self.chatbot_config)
            result = analyst.analyze_content_with_collaboration(content_lines)
            self.communication_hub.save_agent_work("analyst", result, phase="focused_analysis")
        elif focus_area == "processing":
            data_scientist = DataScientistAgent(self.communication_hub, self.chatbot_config)
            result = data_scientist.process_content_with_collaboration(content_lines)
            self.communication_hub.save_agent_work("datascientist", result, phase="focused_processing")
        elif focus_area == "ui":
            ui_designer = UIDesignerAgent(self.communication_hub, self.chatbot_config)
            result = ui_designer.design_ui_with_collaboration([{"q": q, "a": "Sample answer"} for q in content_lines])
            self.communication_hub.save_agent_work("ui_designer", result, phase="focused_ui")
        else:
            result = {"info": f"No specialized agent for focus area '{focus_area}'."}
        return {"success": True, "details": f"Focused development on {focus_area} completed.", "result": result}

    def run_custom_workflow(self, workflow_name, content_lines):
        """Run a custom workflow using WorkflowManager."""
        print(f"Running custom workflow: {workflow_name}")
        workflow_manager = WorkflowManager(self)
        predefined = workflow_manager.get_predefined_workflows()
        if workflow_name in predefined:
            workflow_id = workflow_manager.create_custom_workflow(workflow_name, predefined[workflow_name]["steps"])
            result = workflow_manager.execute_workflow(workflow_id, content_lines)
            self.communication_hub.save_agent_work("chatbot", result, phase=workflow_name)
            return {"success": True, "details": f"Custom workflow '{workflow_name}' completed.", "result": result}
        else:
            return {"success": False, "details": f"Workflow '{workflow_name}' not found."}

    def get_system_status(self):
        """Return system status, including active agents and last saved work."""
        print("Getting system status...")
        last_file = self.communication_hub.file_manager.get_latest_agent_file("chatbot")
        return {
            "system_initialized": True,
            "active_agents": [role.value for role in self.communication_hub.active_agents],
            "last_saved_work": last_file
        }
# === Usage Example and Testing ===

class FileManager:
    """Handles saving and loading agent data to/from files."""

    def __init__(self, base_dir: str = "chatbot_agents"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save_agent_data(self, agent: str, data: dict, phase: str = "") -> str:
        """Save agent data to a JSON file and return the file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent}_{phase}_{timestamp}.json" if phase else f"{agent}_{timestamp}.json"
        filepath = os.path.join(self.base_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def get_latest_agent_file(self, agent: str) -> str:
        """Get the most recent file for the given agent."""
        files = [f for f in os.listdir(self.base_dir) if f.startswith(agent) and f.endswith(".json")]
        if not files:
            return None
        files.sort(reverse=True)
        return os.path.join(self.base_dir, files[0])

    def load_agent_data(self, filepath: str) -> dict:
        """Load agent data from a JSON file."""
        if not os.path.exists(filepath):
            return {}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


def main():
    print("🤖 Multi-Agent Chatbot Development System")
    print("=" * 50)
    
    file_manager = FileManager()
    hub = EnhancedAgentCommunicationHub(file_manager)

    # Register all agents by instantiating them
    agents = [
        AnalystAgent(hub, {}),
        DataScientistAgent(hub, {}),
        UIDesignerAgent(hub, {}),
        FrontendDevAgent(hub, {}),
        BackendDevAgent(hub, {}),
        PromptDesignerAgent(hub, {}),
        PromptEngineerAgent(hub, {}),
        PromptAnalystAgent(hub, {}),
        CoordinatorAgent(hub, {}),
    ]

    # Initialize the application
    app = ChatbotAgentAPP(
        role=AgentRole.CHATBOT,
        communication_hub=hub,
        chatbot_config={}
    )

    # Sample configuration
    chatbot_config = {
        "type": "customer_support",
        "domain": "e-commerce",
        "language": "english",
        "features": ["faq", "product_support", "order_tracking"],
        "integration": ["website", "mobile_app"]
    }
    
    # Initialize with configuration
    app.initialize(chatbot_config)
    
    # Sample content lines (FAQ data)
    sample_content = [
        "What is your return policy?",
        "How do I track my order?",
        "What payment methods do you accept?",
        "How long does shipping take?",
        "Can I cancel my order?",
        "Do you ship internationally?",
        "How do I contact customer support?",
        "What sizes are available?",
        "Are there any discounts available?",
        "How do I create an account?"
    ]
    
    # Example 1: Run full development
    print("\n🚀 Example 1: Full Development Process")
    full_result = app.run_full_development(sample_content)
    print(f"✅ Full development completed: {full_result['success']}")
    
    # Example 2: Run focused development
    print("\n🎯 Example 2: Focused Development (Analysis)")
    focused_result = app.run_focused_development(sample_content, "analysis")
    print(f"✅ Focused development completed: {focused_result['success']}")
    
    # Example 3: Run custom workflow
    print("\n🔧 Example 3: Custom Workflow (Quick Analysis)")
    workflow_result = app.run_custom_workflow("quick_analysis", sample_content)
    print(f"✅ Workflow completed: {workflow_result['success']}")
    
    # Example 4: System status
    print("\n📊 Example 4: System Status")
    status = app.get_system_status()
    print(f"✅ System status retrieved: {status['system_initialized']}")
    
    print("\n🎉 All examples completed successfully!")
    print("📁 Check the 'chatbot_agents' directory for generated files.")

if __name__ == "__main__":
    main()
