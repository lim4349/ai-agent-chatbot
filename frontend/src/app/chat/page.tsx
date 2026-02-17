'use client';

import { useEffect, useState } from 'react';
import { useChatStore, useActiveSession } from '@/stores/chat-store';
import { Header } from '@/components/header/header';
import { Sidebar } from '@/components/sidebar/sidebar';
import { ChatContainer } from '@/components/chat/chat-container';
import { CombinedDocumentUpload } from '@/components/documents/combined-document-upload';
import { ErrorBoundary } from '@/components/error-boundary';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

export default function ChatPage() {
  const sidebarOpen = useChatStore((state) => state.sidebarOpen);
  const toggleSidebar = useChatStore((state) => state.toggleSidebar);
  const hasHydrated = useChatStore((state) => state._hasHydrated);
  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const createSession = useChatStore((state) => state.createSession);
  const activeSession = useActiveSession();

  // Mobile sidebar state (separate from desktop sidebar)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Create initial session only after hydration is complete
  useEffect(() => {
    if (hasHydrated && sessions.length === 0) {
      createSession();
    }
  }, [hasHydrated, sessions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle menu click - different behavior for mobile vs desktop
  const handleMenuClick = () => {
    if (window.innerWidth < 768) {
      // Mobile: toggle Sheet
      setMobileSidebarOpen(true);
    } else {
      // Desktop: toggle sidebar visibility
      toggleSidebar();
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header onMenuClick={handleMenuClick} />

      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Sidebar */}
        <div
          className={cn(
            'hidden md:block transition-all duration-300 w-64',
            sidebarOpen ? 'opacity-100' : 'opacity-0 overflow-hidden w-0'
          )}
        >
          <div className="h-full">
            <Sidebar />
          </div>
        </div>

        {/* Mobile Sidebar (Sheet) */}
        <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
          <SheetContent side="left" className="p-0 w-64">
            <Sidebar onClose={() => setMobileSidebarOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Toolbar */}
          <div className="border-b border-border px-4 py-2 flex items-center justify-between bg-card">
            <div className="text-sm text-muted-foreground">
              {activeSession?.title || 'New Chat'}
            </div>
            <CombinedDocumentUpload />
          </div>

          {/* Chat Container */}
          <ErrorBoundary>
            <ChatContainer />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
