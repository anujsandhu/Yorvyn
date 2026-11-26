/**
 * YORVYN — PHASE 8: Avatar AI Conversation Manager
 * 
 * Manages:
 * 1. Multi-turn dialogue between user and AI Avatar Stylist.
 * 2. Intent parsing pipeline and proposal generation.
 * 3. Quick action suggestions and contextual recommendation follow-ups.
 * 4. Staging proposals into AvatarPreviewOrchestrator.
 */

import { AvatarProfile } from '../../types/avatarProfile';
import { AIMessage, AvatarCustomizationProposal } from './avatarAITypes';
import { AvatarIntentParser } from './avatarIntentParser';
import { AvatarPreviewOrchestrator } from './avatarPreviewOrchestrator';

export type ConversationListener = (messages: AIMessage[]) => void;

export class AvatarAIConversationManager {
  private messages: AIMessage[] = [];
  private previewOrchestrator: AvatarPreviewOrchestrator | null = null;
  private listeners: Set<ConversationListener> = new Set();

  constructor(previewOrchestrator?: AvatarPreviewOrchestrator) {
    if (previewOrchestrator) {
      this.previewOrchestrator = previewOrchestrator;
    }
    this.initializeDefaultChat();
  }

  public setPreviewOrchestrator(orchestrator: AvatarPreviewOrchestrator): void {
    this.previewOrchestrator = orchestrator;
  }

  public getMessages(): AIMessage[] {
    return [...this.messages];
  }

  public clearMessages(): void {
    this.messages = [];
    this.initializeDefaultChat();
    this.notify();
  }

  private initializeDefaultChat(): void {
    this.messages = [
      {
        id: `msg_welcome_${Date.now()}`,
        sender: 'assistant',
        text: "Hello! I'm your Yorvyn Avatar Stylist. You can tell me how you want to adjust your 3D avatar in natural language, upload a reference photo, or ask for occasion styling.",
        timestamp: new Date().toISOString(),
        quickActions: [
          'Give me a modern textured hairstyle',
          'Make my jaw wider & more defined',
          'Make my shoulders broader (+35%)',
          'Give me an athletic body shape',
          'Style me for a luxury evening gala'
        ]
      }
    ];
  }

  /**
   * Process a user message and generate a structured proposal preview.
   */
  public async handleUserMessage(
    userText: string,
    currentProfile: AvatarProfile
  ): Promise<AvatarCustomizationProposal | null> {
    const trimmed = userText.trim();
    if (!trimmed) return null;

    // 1. Add User Message
    const userMsg: AIMessage = {
      id: `msg_user_${Date.now()}`,
      sender: 'user',
      text: trimmed,
      timestamp: new Date().toISOString()
    };
    this.messages.push(userMsg);
    this.notify();

    // 2. Parse Intent into structured proposal
    const proposal = AvatarIntentParser.parse(trimmed, currentProfile);

    // 3. Generate Assistant Response
    if (proposal && proposal.operations.length > 0) {
      const opsSummary = proposal.operations.map((op: any) => `• ${op.displayLabel}`).join('\n');
      const assistantText = `${proposal.explanation}\n\n**Proposed Changes:**\n${opsSummary}\n\nYou can preview this live on your 3D avatar or choose an alternative below.`;

      const assistantMsg: AIMessage = {
        id: `msg_ai_${Date.now()}`,
        sender: 'assistant',
        text: assistantText,
        timestamp: new Date().toISOString(),
        proposal,
        quickActions: [
          'Preview in 3D',
          'Accept Changes',
          'Revert Changes'
        ]
      };

      if (proposal.alternatives && proposal.alternatives.length > 0) {
        proposal.alternatives.forEach((alt: AvatarCustomizationProposal, idx: number) => {
          assistantMsg.quickActions?.push(`Try Option ${idx + 2}: ${alt.title}`);
        });
      }

      this.messages.push(assistantMsg);

      // Auto-preview proposal in orchestrator if available
      if (this.previewOrchestrator) {
        this.previewOrchestrator.startPreview(proposal, currentProfile);
      }
    } else {
      // Fallback response with helpful hints
      const assistantMsg: AIMessage = {
        id: `msg_ai_${Date.now()}`,
        sender: 'assistant',
        text: "I couldn't identify specific avatar parameters for that request. Try phrases like:\n• *'Make my jaw wider'*\n• *'Give me an undercut hairstyle'*\n• *'Give me broader shoulders'*\n• *'Change eye color to emerald green'*",
        timestamp: new Date().toISOString(),
        quickActions: [
          'Make my shoulders broader',
          'Give me a textured fade',
          'Try warm gold skin tone',
          'Athletic body proportions'
        ]
      };
      this.messages.push(assistantMsg);
    }

    this.notify();
    return proposal;
  }

  /**
   * Directly inject a proposal (e.g. from Photo Analysis or Hairstyle Matrix).
   */
  public injectProposal(
    proposal: AvatarCustomizationProposal,
    customMessage: string,
    currentProfile: AvatarProfile
  ): void {
    const assistantMsg: AIMessage = {
      id: `msg_injected_${Date.now()}`,
      sender: 'assistant',
      text: customMessage,
      timestamp: new Date().toISOString(),
      proposal,
      quickActions: ['Preview in 3D', 'Accept Changes', 'Revert Changes']
    };

    this.messages.push(assistantMsg);

    if (this.previewOrchestrator) {
      this.previewOrchestrator.startPreview(proposal, currentProfile);
    }

    this.notify();
  }

  /**
   * User accepts the active proposal via chat.
   */
  public acceptProposal(): void {
    if (this.previewOrchestrator) {
      this.previewOrchestrator.acceptPreview();
    }

    const sysMsg: AIMessage = {
      id: `msg_accepted_${Date.now()}`,
      sender: 'system',
      text: '✓ Customization proposal applied to your 3D avatar profile.',
      timestamp: new Date().toISOString(),
      quickActions: [
        'Explore matching hairstyles',
        'Style an outfit for dinner',
        'Adjust facial features'
      ]
    };
    this.messages.push(sysMsg);
    this.notify();
  }

  /**
   * User rejects the active proposal via chat.
   */
  public rejectProposal(): void {
    if (this.previewOrchestrator) {
      this.previewOrchestrator.rejectPreview();
    }

    const sysMsg: AIMessage = {
      id: `msg_rejected_${Date.now()}`,
      sender: 'system',
      text: '✕ Preview discarded. Your avatar remains in its original state.',
      timestamp: new Date().toISOString(),
      quickActions: [
        'Try different hairstyle',
        'Adjust shoulders',
        'Ask AI for style recommendation'
      ]
    };
    this.messages.push(sysMsg);
    this.notify();
  }

  public subscribe(listener: ConversationListener): () => void {
    this.listeners.add(listener);
    listener(this.getMessages());
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const msgs = this.getMessages();
    this.listeners.forEach(fn => fn(msgs));
  }
}

export const avatarAIConversationManager = new AvatarAIConversationManager();
