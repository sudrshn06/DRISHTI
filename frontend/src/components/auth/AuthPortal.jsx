import { useState } from 'react';
import { AlertCircle, CheckCircle2, User, Mail, Lock, UserCheck, ArrowRight } from 'lucide-react';
import { loginUser, registerUser, getCurrentUser } from '../../services/api';
import drishtiFullLogo from '../../assets/branding/drishti-logo-full.png';

export default function AuthPortal({ onAuthSuccess }) {
  const [authMode, setAuthMode] = useState('signin'); // 'signin' | 'signup'
  
  // Sign In Form State
  const [signInForm, setSignInForm] = useState({
    username: '',
    password: '',
  });

  // Sign Up Form State
  const [signUpForm, setSignUpForm] = useState({
    fullName: '',
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  const handleSignIn = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (!signInForm.username.trim() || !signInForm.password) {
      setErrorMessage('Please enter both your username/email and password.');
      return;
    }

    setLoading(true);
    try {
      await loginUser({
        username: signInForm.username.trim(),
        password: signInForm.password,
      });
      const user = await getCurrentUser();
      if (onAuthSuccess) {
        onAuthSuccess(user);
      }
    } catch (err) {
      setErrorMessage(
        err.response?.data?.detail ||
        err.message ||
        'Authentication failed. Please verify your credentials.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    // Client-side validations
    const fullName = signUpForm.fullName.trim();
    const username = signUpForm.username.trim();
    const email = signUpForm.email.trim();
    const password = signUpForm.password;
    const confirmPassword = signUpForm.confirmPassword;

    if (!fullName) {
      setErrorMessage('Full name is required.');
      return;
    }
    if (!username || username.length < 3) {
      setErrorMessage('Username must be at least 3 characters.');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      setErrorMessage('Please enter a valid email address.');
      return;
    }
    if (!password || password.length < 8) {
      setErrorMessage('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);
    try {
      await registerUser({
        full_name: fullName,
        username: username,
        email: email,
        password: password,
      });

      // Switch to sign in mode with pre-populated username & success message
      setSuccessMessage('Account created successfully. Sign in to continue.');
      setSignInForm({
        username: username,
        password: '',
      });
      setSignUpForm({
        fullName: '',
        username: '',
        email: '',
        password: '',
        confirmPassword: '',
      });
      setAuthMode('signin');
    } catch (err) {
      setErrorMessage(
        err.response?.data?.detail ||
        err.message ||
        'Registration failed. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f7f9] text-slate-900">
      <div className="bg-[#102a43] px-5 py-2 text-xs font-semibold tracking-wide text-white">Packaged Commodity Inspection &amp; Decision Support</div>
      <div className="mx-auto grid min-h-[calc(100vh-32px)] max-w-[1100px] items-stretch p-4 sm:p-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
      <aside className="hidden min-h-[560px] flex-col justify-between bg-[#163a5f] p-10 text-white lg:flex">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-100">Government regulatory workspace</p>
          <h1 className="mt-5 text-4xl font-bold leading-tight">Consistent inspection.<br />Defensible decisions.</h1>
          <p className="mt-5 max-w-md text-sm leading-7 text-blue-50">A secure officer portal for packaged commodity capture, statutory review, evidence records and approved reports.</p>
        </div>
        <div className="border-t border-blue-300/40 pt-6 text-xs leading-6 text-blue-100">
          Legal Metrology and food-labelling rules remain deterministic. Every final report requires officer approval.
        </div>
      </aside>
      <div className="w-full border border-slate-300 border-t-4 border-t-blue-900 bg-white p-6 shadow-sm sm:p-8 lg:min-h-[560px] lg:border-l-0 lg:border-t lg:border-t-slate-300 lg:py-14">
        <div className="mb-7 flex justify-center">
          <img
            src={drishtiFullLogo}
            alt="DRISHTI — Packaged Commodity Inspection Portal — Every Label Counts"
            className="h-auto w-full max-w-[340px] object-contain sm:max-w-[360px]"
          />
        </div>

        <h2 className="text-center text-xl font-bold text-slate-800 dark:text-slate-100 mb-6">
          {authMode === 'signin' ? 'Inspector Sign In' : 'Create Inspector Account'}
        </h2>

        {/* Error Notification */}
        {errorMessage && (
          <div className="mb-5 p-3.5 bg-rose-50 dark:bg-rose-900/30 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 rounded-lg flex items-start gap-2.5 text-xs animate-fadeIn">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Success Notification */}
        {successMessage && (
          <div className="mb-5 p-3.5 bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 rounded-lg flex items-start gap-2.5 text-xs animate-fadeIn">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* SIGN IN FORM */}
        {authMode === 'signin' ? (
          <form onSubmit={handleSignIn} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Username or Email
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  autoFocus
                  value={signInForm.username}
                  onChange={(e) => setSignInForm({ ...signInForm, username: e.target.value })}
                  placeholder="Enter your username or email"
                  className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <User className="w-4 h-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type="password"
                  required
                  value={signInForm.password}
                  onChange={(e) => setSignInForm({ ...signInForm, password: e.target.value })}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <Lock className="w-4 h-4 text-slate-400 absolute right-3 top-3 pointer-events-none" />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors shadow-sm disabled:opacity-60 flex items-center justify-center gap-2 cursor-pointer"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-700 text-center">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Don't have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setErrorMessage('');
                    setSuccessMessage('');
                    setAuthMode('signup');
                  }}
                  className="font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer ml-1"
                >
                  Create account
                </button>
              </p>
            </div>
          </form>
        ) : (
          /* SIGN UP FORM */
          <form onSubmit={handleSignUp} className="space-y-3.5">
            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Full Name
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  autoFocus
                  value={signUpForm.fullName}
                  onChange={(e) => setSignUpForm({ ...signUpForm, fullName: e.target.value })}
                  placeholder="e.g. Officer Rajesh Sharma"
                  className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <UserCheck className="w-4 h-4 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Username
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={signUpForm.username}
                  onChange={(e) => setSignUpForm({ ...signUpForm, username: e.target.value })}
                  placeholder="e.g. rajesh_sharma"
                  className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <User className="w-4 h-4 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Official Email
              </label>
              <div className="relative">
                <input
                  type="email"
                  required
                  value={signUpForm.email}
                  onChange={(e) => setSignUpForm({ ...signUpForm, email: e.target.value })}
                  placeholder="e.g. rajesh@drishti.gov.in"
                  className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <Mail className="w-4 h-4 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Password <span className="text-slate-400 font-normal">(min 8 characters)</span>
              </label>
              <div className="relative">
                <input
                  type="password"
                  required
                  minLength={8}
                  value={signUpForm.password}
                  onChange={(e) => setSignUpForm({ ...signUpForm, password: e.target.value })}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <Lock className="w-4 h-4 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  type="password"
                  required
                  minLength={8}
                  value={signUpForm.confirmPassword}
                  onChange={(e) => setSignUpForm({ ...signUpForm, confirmPassword: e.target.value })}
                  placeholder="••••••••••••"
                  className="w-full px-3.5 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 dark:text-slate-100 placeholder:text-slate-400"
                />
                <Lock className="w-4 h-4 text-slate-400 absolute right-3 top-2.5 pointer-events-none" />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-lg text-sm transition-colors shadow-sm disabled:opacity-60 flex items-center justify-center gap-2 cursor-pointer"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Creating account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight size={16} />
                </>
              )}
            </button>

            <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-700 text-center">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Already have an account?{' '}
                <button
                  type="button"
                  onClick={() => {
                    setErrorMessage('');
                    setSuccessMessage('');
                    setAuthMode('signin');
                  }}
                  className="font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer ml-1"
                >
                  Sign in
                </button>
              </p>
            </div>
          </form>
        )}
      </div>
      </div>
    </div>
  );
}
