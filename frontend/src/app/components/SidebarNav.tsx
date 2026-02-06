import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
}

interface SidebarNavProps {
  navigation: NavItem[];
  collapsed: boolean;
  pathname: string;
}

export default function SidebarNav({ navigation, collapsed, pathname }: SidebarNavProps) {
  return (
    <nav className="flex-1 px-2 py-4 space-y-1">
      {navigation.map((item) => {
        const isActive =
          pathname === item.href ||
          (item.href !== '/console' && pathname.startsWith(item.href));

        const link = (
          <Link
            key={item.name}
            to={item.href}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'flex items-center rounded-md text-sm font-medium transition-colors',
              collapsed ? 'justify-center px-2 py-2' : 'px-4 py-2',
              isActive
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-sidebar-muted-foreground hover:bg-sidebar-accent/50'
            )}
          >
            <item.icon className={cn('h-5 w-5 shrink-0', !collapsed && 'mr-3')} />
            {!collapsed && <span>{item.name}</span>}
          </Link>
        );

        if (collapsed) {
          return (
            <Tooltip key={item.name} delayDuration={0}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{item.name}</TooltipContent>
            </Tooltip>
          );
        }

        return link;
      })}
    </nav>
  );
}
