import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from 'react-oidc-context';
import {
  LayoutDashboard,
  FileText,
  FileCode,
  Link2,
  LogOut,
  User,
} from 'lucide-react';

const navigation = [
  { name: 'Dashboard', href: '/console', icon: LayoutDashboard },
  { name: 'DPPs', href: '/console/dpps', icon: FileText },
  { name: 'Templates', href: '/console/templates', icon: FileCode },
  { name: 'Connectors', href: '/console/connectors', icon: Link2 },
];

export default function PublisherLayout() {
  const auth = useAuth();
  const location = useLocation();

  const handleLogout = () => {
    auth.signoutRedirect();
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-64 bg-gray-900">
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center h-16 px-4 bg-gray-800">
            <span className="text-xl font-bold text-white">DPP Platform</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-2 py-4 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href ||
                (item.href !== '/console' && location.pathname.startsWith(item.href));

              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={`flex items-center px-4 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'bg-gray-800 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  <item.icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          {/* User section */}
          <div className="p-4 border-t border-gray-700">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <User className="h-8 w-8 text-gray-400" />
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-white">
                  {auth.user?.profile?.preferred_username || 'User'}
                </p>
                <p className="text-xs text-gray-400">
                  {auth.user?.profile?.email || ''}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="mt-3 w-full flex items-center justify-center px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white rounded-md"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="pl-64">
        <main className="p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
