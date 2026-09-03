CREATE TABLE "auth_users" (
    "id" TEXT NOT NULL,
    "name" TEXT,
    "email" TEXT NOT NULL,
    "email_verified" TIMESTAMPTZ(3),
    "password_hash" TEXT,
    "role" TEXT,

    CONSTRAINT "pk_auth_users" PRIMARY KEY ("id")
);

CREATE TABLE "auth_accounts" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "provider_account_id" TEXT NOT NULL,
    "refresh_token" TEXT,
    "access_token" TEXT,
    "expires_at" INTEGER,
    "token_type" TEXT,
    "scope" TEXT,
    "id_token" TEXT,
    "session_state" TEXT,

    CONSTRAINT "pk_auth_accounts" PRIMARY KEY ("id"),
    CONSTRAINT "fk_auth_accounts_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_users"("id") ON DELETE CASCADE
);

CREATE TABLE "auth_sessions" (
    "id" TEXT NOT NULL,
    "session_token" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "expires" TIMESTAMPTZ(3) NOT NULL,

    CONSTRAINT "pk_auth_sessions" PRIMARY KEY ("id"),
    CONSTRAINT "fk_auth_sessions_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_users"("id") ON DELETE CASCADE
);

CREATE TABLE "auth_verification_tokens" (
    "identifier" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "expires" TIMESTAMPTZ(3) NOT NULL
);

CREATE UNIQUE INDEX "uq_auth_users_email" ON "auth_users"("email");
CREATE INDEX "ix_auth_accounts_user_id" ON "auth_accounts"("user_id");
CREATE UNIQUE INDEX "uq_auth_accounts_provider_provider_account_id"
    ON "auth_accounts"("provider", "provider_account_id");
CREATE INDEX "ix_auth_sessions_user_id" ON "auth_sessions"("user_id");
CREATE UNIQUE INDEX "uq_auth_sessions_session_token"
    ON "auth_sessions"("session_token");
CREATE UNIQUE INDEX "uq_auth_verification_tokens_token"
    ON "auth_verification_tokens"("token");
CREATE UNIQUE INDEX "uq_auth_verification_tokens_identifier_token"
    ON "auth_verification_tokens"("identifier", "token");
