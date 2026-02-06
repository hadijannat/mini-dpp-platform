import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import { Fingerprint, LogIn, LayoutDashboard, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

const navLinks = [
  { label: 'What is DPP?', href: '#what-is-dpp' },
  { label: 'Standards', href: '#standards' },
  { label: 'Features', href: '#features' },
];

export default function LandingHeader() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleSignIn = () => auth.signinRedirect();
  const handleDashboard = () => navigate('/console');

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand */}
        <a href="#" className="flex items-center gap-2 font-semibold">
          <Fingerprint className="h-5 w-5 text-primary" />
          <span>DPP Platform</span>
        </a>

        {/* Desktop nav */}
        <nav className="hidden items-center gap-6 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Desktop auth */}
        <div className="hidden items-center gap-2 md:flex">
          {auth.isAuthenticated ? (
            <Button size="sm" onClick={handleDashboard}>
              <LayoutDashboard className="mr-1.5 h-4 w-4" />
              Dashboard
            </Button>
          ) : (
            <Button size="sm" onClick={handleSignIn}>
              <LogIn className="mr-1.5 h-4 w-4" />
              Sign in
            </Button>
          )}
        </div>

        {/* Mobile hamburger */}
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Open menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-64">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Fingerprint className="h-5 w-5 text-primary" />
                DPP Platform
              </SheetTitle>
            </SheetHeader>
            <nav className="mt-6 flex flex-col gap-4">
              {navLinks.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {link.label}
                </a>
              ))}
              <div className="mt-4 border-t pt-4">
                {auth.isAuthenticated ? (
                  <Button
                    className="w-full"
                    size="sm"
                    onClick={() => {
                      setMobileOpen(false);
                      handleDashboard();
                    }}
                  >
                    <LayoutDashboard className="mr-1.5 h-4 w-4" />
                    Dashboard
                  </Button>
                ) : (
                  <Button
                    className="w-full"
                    size="sm"
                    onClick={() => {
                      setMobileOpen(false);
                      handleSignIn();
                    }}
                  >
                    <LogIn className="mr-1.5 h-4 w-4" />
                    Sign in
                  </Button>
                )}
              </div>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
