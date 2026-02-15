'use client';

import { Menu, Moon, Sun, Bot, Languages } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { HealthIndicator } from './health-indicator';
import { useTranslation } from '@/lib/i18n';

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { locale, t, toggleLocale } = useTranslation();

  const toggleTheme = () => {
    document.documentElement.classList.toggle('dark');
  };

  return (
    <header className="h-14 border-b border-border bg-card flex items-center justify-between px-4">
      {/* Left section */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onMenuClick}
        >
          <Menu className="w-5 h-5" />
        </Button>

        <div className="flex items-center gap-2">
          <Bot className="w-6 h-6 text-primary" />
          <h1 className="text-lg font-semibold">{t('header.title')}</h1>
        </div>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-1">
        <HealthIndicator />

        <Button
          variant="ghost"
          size="sm"
          onClick={toggleLocale}
          className="text-xs font-medium px-2.5 gap-1.5"
          title={locale === 'ko' ? 'Switch to English' : '한국어로 전환'}
        >
          <Languages className="w-4 h-4" />
          <span>{locale === 'ko' ? 'EN' : '한'}</span>
        </Button>

        <Button variant="ghost" size="icon" onClick={toggleTheme}>
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </header>
  );
}
