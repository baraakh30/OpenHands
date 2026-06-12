import React from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router";
import { useIsAuthed } from "#/hooks/query/use-is-authed";
import { useConfig } from "#/hooks/query/use-config";
import AuthService from "#/api/auth-service/auth-service.api";
import { useGitHubAuthUrl } from "#/hooks/use-github-auth-url";
import { useEmailVerification } from "#/hooks/use-email-verification";
import { useInvitation } from "#/hooks/use-invitation";
import { LoginContent } from "#/components/features/auth/login-content";
import { EmailVerificationModal } from "#/components/features/waitlist/email-verification-modal";
import { RequestSubmittedModal } from "#/components/features/onboarding/request-submitted-modal";

interface LocationState {
  showRequestSubmittedModal?: boolean;
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const returnTo = searchParams.get("returnTo") || "/";
  const locationState = location.state as LocationState | null;

  const config = useConfig();
  const { data: isAuthed, isLoading: isAuthLoading } = useIsAuthed();
  const {
    emailVerified,
    hasDuplicatedEmail,
    recaptchaBlocked,
    wasRateLimited,
    emailVerificationModalOpen,
    setEmailVerificationModalOpen,
    userId,
  } = useEmailVerification();

  const { hasInvitation, buildOAuthStateData } = useInvitation();

  const gitHubAuthUrl = useGitHubAuthUrl({
    appMode: config.data?.app_mode || null,
    authUrl: config.data?.auth_url,
  });

  const [showRequestModal, setShowRequestModal] = React.useState(
    () => locationState?.showRequestSubmittedModal ?? false,
  );

  const handleRequestModalClose = () => {
    setShowRequestModal(false);
    navigate(location.pathname, { replace: true, state: {} });
  };

  // Redirect OSS mode users to home — unless basic auth is required
  React.useEffect(() => {
    if (
      !config.isLoading &&
      config.data?.app_mode === "oss" &&
      !config.data?.basic_auth_required
    ) {
      navigate("/", { replace: true });
    }
  }, [config.isLoading, config.data?.app_mode, config.data?.basic_auth_required, navigate]);

  // Redirect authenticated users away from login page
  // Preserve login_method param so useAuthCallback can store it for auto-login
  React.useEffect(() => {
    if (!isAuthLoading && isAuthed) {
      const loginMethod = searchParams.get("login_method");
      let destination = returnTo;
      if (loginMethod) {
        const separator = returnTo.includes("?") ? "&" : "?";
        destination = `${returnTo}${separator}login_method=${encodeURIComponent(loginMethod)}`;
      }
      navigate(destination, { replace: true });
    }
  }, [isAuthed, isAuthLoading, navigate, returnTo, searchParams]);

  if (isAuthLoading || config.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white" />
      </div>
    );
  }

  // Don't render login content if user is authenticated
  if (isAuthed) {
    return null;
  }

  // OSS + basic auth gate: show a simple username/password form
  if (
    config.data?.app_mode === "oss" &&
    config.data?.basic_auth_required
  ) {
    return <BasicAuthLoginForm returnTo={returnTo} />;
  }

  // OSS without basic auth: nothing to show (redirect handled above)
  if (config.data?.app_mode === "oss") {
    return null;
  }

  return (
    <>
      <main
        className="min-h-screen flex items-center justify-center bg-base p-4"
        data-testid="login-page"
      >
        <LoginContent
          githubAuthUrl={gitHubAuthUrl}
          appMode={config.data?.app_mode}
          authUrl={config.data?.auth_url}
          providersConfigured={config.data?.providers_configured}
          emailVerified={emailVerified}
          hasDuplicatedEmail={hasDuplicatedEmail}
          recaptchaBlocked={recaptchaBlocked}
          hasInvitation={hasInvitation}
          buildOAuthStateData={buildOAuthStateData}
        />
      </main>

      {emailVerificationModalOpen && (
        <EmailVerificationModal
          onClose={() => {
            setEmailVerificationModalOpen(false);
          }}
          userId={userId}
          wasRateLimited={wasRateLimited}
        />
      )}

      {showRequestModal && (
        <RequestSubmittedModal onClose={handleRequestModalClose} />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Basic-auth login form (OSS deployments with OPENHANDS_BASIC_AUTH_* set)
// ---------------------------------------------------------------------------
function BasicAuthLoginForm({ returnTo }: { returnTo: string }) {
  const navigate = useNavigate();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await AuthService.basicAuthLogin(username, password);
      navigate(returnTo, { replace: true });
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-base p-4">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 w-full max-w-sm bg-tertiary border border-[#717888] rounded-xl p-8"
        data-testid="basic-auth-login-form"
      >
        <h1 className="text-white text-xl font-semibold text-center">
          Sign in to OpenHands
        </h1>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm text-white" htmlFor="basic-auth-username">
            Username
          </label>
          <input
            id="basic-auth-username"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="bg-[#1c1e24] border border-[#717888] rounded-sm px-3 py-2 text-white placeholder:italic placeholder:text-gray-500 focus:outline-none focus:border-white"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm text-white" htmlFor="basic-auth-password">
            Password
          </label>
          <input
            id="basic-auth-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-[#1c1e24] border border-[#717888] rounded-sm px-3 py-2 text-white placeholder:italic placeholder:text-gray-500 focus:outline-none focus:border-white"
          />
        </div>

        {error && (
          <p className="text-red-400 text-sm text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="mt-2 bg-white text-black font-medium rounded-sm py-2 hover:bg-gray-200 disabled:opacity-50 transition-colors"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
