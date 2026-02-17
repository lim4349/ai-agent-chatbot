'use client';

import { useChatStore } from '@/stores/chat-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { SessionItem } from './session-item';
import { NewSessionButton } from './new-session-button';
import { useTranslation } from '@/lib/i18n';

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const createSession = useChatStore((state) => state.createSession);
  const switchSession = useChatStore((state) => state.switchSession);
  const deleteSession = useChatStore((state) => state.deleteSession);
  const { t } = useTranslation();

  const handleSessionSelect = (sessionId: string) => {
    switchSession(sessionId);
    onClose?.();
  };

  const handleNewSession = async () => {
    await createSession();
    onClose?.();
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-card border-r border-border">
      {/* Header */}
      <div className="flex-shrink-0 p-4">
        <h2 className="text-lg font-semibold">{t('sidebar.title')}</h2>
      </div>

      {/* New Chat Button */}
      <div className="flex-shrink-0 px-4 pb-4">
        <NewSessionButton onClick={handleNewSession} />
      </div>

      <Separator className="flex-shrink-0" />

      {/* Session List */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="p-2 space-y-1">
            {sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                isActive={session.id === activeSessionId}
                onSelect={() => handleSessionSelect(session.id)}
                onDelete={async () => {
                  await deleteSession(session.id);
                }}
              />
            ))}

            {sessions.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                {t('sidebar.empty')}
              </p>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 p-4 border-t border-border">
        <p className="text-xs text-muted-foreground text-center">
          {t('sidebar.count', sessions.length)}
        </p>
      </div>
    </div>
  );
}
