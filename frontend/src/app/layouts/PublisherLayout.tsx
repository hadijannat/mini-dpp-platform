import { useState, useEffect, useCallback } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import {
  LayoutDashboard,
  FileText,
  FileCode,
  Link2,
  QrCode,
  Layers,
  Settings,
  Users,
  ShieldCheck,
  Activity,
  ScrollText,
  ChevronLeft,
  ChevronRight,
  Menu,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { isAdmin as checkIsAdmin } from '@/lib/auth';
import { useBreadcrumbs } from '@/lib/breadcrumbs';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import SidebarNav, { type NavItem } from '../components/SidebarNav';
import SidebarUserFooter from '../components/SidebarUserFooter';

const STORAGE_KEY = 'sidebar-collapsed';
const SIDEBAR_FULL = 256;
const SIDEBAR_COLLAPSED = 48;

const baseNavigation: NavItem[] = [
  { name: 'Dashboard', href: '/console', icon: LayoutDashboard },
  { name: 'DPPs', href: '/console/dpps', icon: FileText },
  { name: 'Masters', href: '/console/masters', icon: Layers },
  { name: 'Templates', href: '/console/templates', icon: FileCode },
  { name: 'Data Carriers', href: '/console/carriers', icon: QrCode },
  { name: 'Connectors', href: '/console/connectors', icon: Link2 },
  { name: 'Compliance', href: '/console/compliance', icon: ShieldCheck },
  { name: 'Supply Chain', href: '/console/epcis', icon: Activity },
];

function getInitials(name: string | undefined): string {
  if (!name) return '?';
  return name
    .split(/[\s._-]+/)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? '')
    .join('');
}

export default function PublisherLayout() {
  const auth = useAuth();
  const location = useLocation();
  const breadcrumbs = useBreadcrumbs();
  const userIsAdmin = checkIsAdmin(auth.user);

  const navigation: NavItem[] = userIsAdmin
    ? [
        ...baseNavigation,
        { name: 'Audit Trail', href: '/console/audit', icon: ScrollText },
        { name: 'Tenants', href: '/console/tenants', icon: Users },
        { name: 'Settings', href: '/console/settings', icon: Settings },
      ]
    : baseNavigation;

  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  // Close mobile sheet on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const username = auth.user?.profile?.preferred_username as string | undefined;
  const initials = getInitials(username);
  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_FULL;

  const sidebarContent = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Logo */}
      <div className={cn('flex h-14 items-center border-b border-sidebar-border', collapsed ? 'justify-center px-2' : 'px-4')}>
        {collapsed ? (
          <span className="text-lg font-bold">D</span>
        ) : (
          <span className="text-lg font-bold">DPP Platform</span>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1">
        <SidebarNav navigation={navigation} collapsed={collapsed} pathname={location.pathname} />
      </ScrollArea>

      {/* User footer */}
      <SidebarUserFooter collapsed={collapsed} />
    </div>
  );

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        {/* Skip to content link for keyboard users */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-md focus:ring-2 focus:ring-ring"
        >
          Skip to content
        </a>

        {/* Desktop sidebar */}
        <aside
          className="fixed inset-y-0 left-0 z-30 hidden border-r border-sidebar-border transition-[width] duration-200 ease-in-out md:block"
          style={{ width: sidebarWidth }}
        >
          {sidebarContent}

          {/* Collapse toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="absolute -right-3 top-[18px] z-40 h-6 w-6 rounded-full border bg-background shadow-sm"
          >
            {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
          </Button>
        </aside>

        {/* Mobile sheet */}
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetContent side="left" className="w-64 p-0 [&>button]:hidden">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
              <div className="flex h-14 items-center border-b border-sidebar-border px-4">
                <span className="text-lg font-bold">DPP Platform</span>
              </div>
              <ScrollArea className="flex-1">
                <SidebarNav navigation={navigation} collapsed={false} pathname={location.pathname} />
              </ScrollArea>
              <SidebarUserFooter collapsed={false} />
            </div>
          </SheetContent>
        </Sheet>

        {/* Main area */}
        <div
          className={cn('transition-[margin-left] duration-200 ease-in-out md:ml-[var(--sidebar-w)]')}
          style={{ '--sidebar-w': `${sidebarWidth}px` } as React.CSSProperties}
        >
          {/* Top bar */}
          <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b bg-background/80 px-4 backdrop-blur">
            {/* Mobile menu button */}
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
            </Button>

            {/* Breadcrumbs */}
            <Breadcrumb className="hidden sm:flex">
              <BreadcrumbList>
                {breadcrumbs.map((item, index) => (
                  <BreadcrumbItem key={item.label + index}>
                    {index > 0 && <BreadcrumbSeparator />}
                    {item.href ? (
                      <BreadcrumbLink asChild>
                        <Link to={item.href}>{item.label}</Link>
                      </BreadcrumbLink>
                    ) : (
                      <BreadcrumbPage>{item.label}</BreadcrumbPage>
                    )}
                  </BreadcrumbItem>
                ))}
              </BreadcrumbList>
            </Breadcrumb>

            <div className="flex-1" />

            {/* User avatar dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <Avatar className="h-8 w-8">
                    <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => auth.signoutRedirect()}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>

          {/* Page content */}
          <main id="main-content" className="p-6 md:p-8">
            <Outlet />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
