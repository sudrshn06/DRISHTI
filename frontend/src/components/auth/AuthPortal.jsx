import { useState } from 'react';
import { AlertCircle, CheckCircle2, User, Mail, Lock, UserCheck, ArrowRight } from 'lucide-react';
import { loginUser, registerUser, getCurrentUser } from '../../services/api';
import drishtiFullLogo from '../../assets/branding/drishti-logo-full.png';

export default function AuthPortal({ onAuthSuccess }) {
  const [authMode, setAuthMode] = useState('signin');
  const [signInForm, setSignInForm] = useState({ username: '', password: '' });
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
      await loginUser({ username: signInForm.username.trim(), password: signInForm.password });
      const user = await getCurrentUser();
      if (onAuthSuccess) onAuthSuccess(user);
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

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
      await registerUser({ full_name: fullName, username, email, password });
      setSuccessMessage('Account created successfully. Sign in to continue.');
      setSignInForm({ username, password: '' });
      setSignUpForm({ fullName: '', username: '', email: '', password: '', confirmPassword: '' });
      setAuthMode('signin');
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || err.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f4f7f8] text-slate-900">
      <div className="bg-[#102a43] px-5 py-2 text-[10px] font-extrabold uppercase tracking-[0.14em] text-white">
        Packaged Commodity Inspection &amp; Decision Support
      </div>

      <div className="mx-auto grid min-h-[calc(100vh-32px)] max-w-[1120px] items-stretch p-4 sm:p-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
        <aside className="relative hidden min-h-[590px] flex-col justify-between overflow-hidden rounded-l-[22px] bg-gradient-to-br from-[#102a43] via-[#163a5f] to-[#0d5f63] p-10 text-white shadow-[0_24px_60px_rgba(16,42,67,0.16)] lg:flex">
          <div className="relative z-10">
            <p className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-teal-100">Government regulatory workspace</p>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.12] tracking-tight">Consistent inspection.<br />Defensible decisions.</h1>
            <p className="mt-5 max-w-md text-sm leading-7 text-slate-100/90">A secure officer portal for packaged commodity capture, statutory review, traceable evidence and approved inspection reports.</p>

            <div className="mt-8 grid gap-3 text-xs text-white/85 sm:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5">
                <p className="font-bold text-white">Evidence first</p>
                <p className="mt-1 leading-5">Machine observations stay linked to photographs and officer review.</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-3.5">
                <p className="font-bold text-white">Officer controlled</p>
                <p className="mt-1 leading-5">Final findings remain subject to inspector confirmation and approval.</p>
              </div>
            </div>
          </div>

          <div className="relative z-10 border-t border-white/15 pt-6 text-xs leading-6 text-slate-200">
            Legal Metrology and food-labelling checks remain deterministic. Unclear evidence is routed to review rather than treated as a violation.
          </div>
        </aside>

        <div className="w-full rounded-[22px] border border-slate-200 bg-white p-6 shadow-[0_24px_60px_rgba(16,42,67,0.12)] sm:p-8 lg:min-h-[590px] lg:rounded-l-none lg:py-12">
          <div className="mb-6 flex justify-center">
            <img src={drishtiFullLogo} alt="DRISHTI — Packaged Commodity Inspection Portal — Every Label Counts" className="h-auto w-full max-w-[330px] object-contain" />
          </div>

          <div className="mb-6 text-center">
            <p className="text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#087f83]">Secure officer access</p>
            <h2 className="mt-1 text-xl font-extrabold tracking-tight text-[#102a43]">{authMode === 'signin' ? 'Inspector Sign In' : 'Create Inspector Account'}</h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">{authMode === 'signin' ? 'Sign in to continue to your inspection workspace.' : 'Create an account for the DRISHTI inspection workspace.'}</p>
          </div>

          {errorMessage && (
            <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-xs text-emerald-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /><span>{successMessage}</span>
            </div>
          )}

          {authMode === 'signin' ? (
            <form onSubmit={handleSignIn} className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Username or Email</label>
                <div className="relative">
                  <input type="text" required autoFocus value={signInForm.username} onChange={(e) => setSignInForm({ ...signInForm, username: e.target.value })} placeholder="Enter your username or email" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 pr-10 text-sm placeholder:text-slate-400" />
                  <User className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Password</label>
                <div className="relative">
                  <input type="password" required value={signInForm.password} onChange={(e) => setSignInForm({ ...signInForm, password: e.target.value })} placeholder="••••••••••••" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 pr-10 text-sm placeholder:text-slate-400" />
                  <Lock className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <button type="submit" disabled={loading} className="mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#102a43] py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#163a5f] disabled:opacity-60">
                {loading ? <><div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div><span>Signing in...</span></> : <><span>Sign In</span><ArrowRight size={16} /></>}
              </button>

              <div className="mt-6 border-t border-slate-100 pt-4 text-center">
                <p className="text-xs text-slate-500">Don't have an account?{' '}
                  <button type="button" onClick={() => { setErrorMessage(''); setSuccessMessage(''); setAuthMode('signup'); }} className="ml-1 font-extrabold text-[#087f83] hover:underline">Create account</button>
                </p>
              </div>
            </form>
          ) : (
            <form onSubmit={handleSignUp} className="space-y-3.5">
              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Full Name</label>
                <div className="relative">
                  <input type="text" required autoFocus value={signUpForm.fullName} onChange={(e) => setSignUpForm({ ...signUpForm, fullName: e.target.value })} placeholder="e.g. Officer Rajesh Sharma" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 pr-10 text-sm placeholder:text-slate-400" />
                  <UserCheck className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Username</label>
                <div className="relative">
                  <input type="text" required value={signUpForm.username} onChange={(e) => setSignUpForm({ ...signUpForm, username: e.target.value })} placeholder="e.g. rajesh_sharma" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 pr-10 text-sm placeholder:text-slate-400" />
                  <User className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Official Email</label>
                <div className="relative">
                  <input type="email" required value={signUpForm.email} onChange={(e) => setSignUpForm({ ...signUpForm, email: e.target.value })} placeholder="e.g. rajesh@drishti.gov.in" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 pr-10 text-sm placeholder:text-slate-400" />
                  <Mail className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Password <span className="font-normal text-slate-400">(min 8 characters)</span></label>
                <div className="relative">
                  <input type="password" required minLength={8} value={signUpForm.password} onChange={(e) => setSignUpForm({ ...signUpForm, password: e.target.value })} placeholder="••••••••••••" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 pr-10 text-sm placeholder:text-slate-400" />
                  <Lock className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-bold text-slate-700">Confirm Password</label>
                <div className="relative">
                  <input type="password" required minLength={8} value={signUpForm.confirmPassword} onChange={(e) => setSignUpForm({ ...signUpForm, confirmPassword: e.target.value })} placeholder="••••••••••••" className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2 pr-10 text-sm placeholder:text-slate-400" />
                  <Lock className="pointer-events-none absolute right-3 top-2.5 h-4 w-4 text-slate-400" />
                </div>
              </div>

              <button type="submit" disabled={loading} className="mt-2 flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#102a43] py-3 text-sm font-extrabold text-white shadow-sm hover:bg-[#163a5f] disabled:opacity-60">
                {loading ? <><div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div><span>Creating account...</span></> : <><span>Create Account</span><ArrowRight size={16} /></>}
              </button>

              <div className="mt-6 border-t border-slate-100 pt-4 text-center">
                <p className="text-xs text-slate-500">Already have an account?{' '}
                  <button type="button" onClick={() => { setErrorMessage(''); setSuccessMessage(''); setAuthMode('signin'); }} className="ml-1 font-extrabold text-[#087f83] hover:underline">Sign in</button>
                </p>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
