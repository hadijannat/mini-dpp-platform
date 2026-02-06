import { useAuth } from 'react-oidc-context';
import { LogOut } from 'lucide-react';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import TenantSelector from './TenantSelector';

interface SidebarUserFooterProps {
  collapsed: boolean;
}

function getInitials(name: string | undefined): string {
  if (!name) return '?';
  return name
    .split(/[\s._-]+/)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? '')
    .join('');
}

export default function SidebarUserFooter({ collapsed }: SidebarUserFooterProps) {
  const auth = useAuth();
  const username = auth.user?.profile?.preferred_username as string | undefined;
  const email = auth.user?.profile?.email as string | undefined;
  const initials = getInitials(username);

  const handleLogout = () => {
    auth.signoutRedirect();
  };

  if (collapsed) {
    return (
      <div className="p-2">
        <Separator className="mb-2 bg-sidebar-border" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex w-full items-center justify-center rounded-md p-1 hover:bg-sidebar-accent/50">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-sidebar-accent text-sidebar-accent-foreground text-xs">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="right" align="end" className="w-56">
            <DropdownMenuLabel>
              <p className="text-sm font-medium">{username || 'User'}</p>
              {email && <p className="text-xs text-muted-foreground">{email}</p>}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    );
  }

  return (
    <div className="p-4">
      <Separator className="mb-4 bg-sidebar-border" />
      <div className="flex items-center gap-3">
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="bg-sidebar-accent text-sidebar-accent-foreground text-xs">
            {initials}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-sidebar-foreground">
            {username || 'User'}
          </p>
          {email && (
            <p className="truncate text-xs text-sidebar-muted-foreground">{email}</p>
          )}
        </div>
      </div>
      <TenantSelector />
      <button
        onClick={handleLogout}
        className="mt-3 flex w-full items-center justify-center rounded-md px-4 py-2 text-sm font-medium text-sidebar-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
      >
        <LogOut className="mr-2 h-4 w-4" />
        Sign out
      </button>
    </div>
  );
}
