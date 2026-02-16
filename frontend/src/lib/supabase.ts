import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let supabaseInstance: ReturnType<typeof createClient> | null = null;

/**
 * Get Supabase client instance
 * Lazily initialized to avoid build errors when env vars are not set
 */
function getSupabaseClient() {
  if (supabaseInstance) {
    return supabaseInstance;
  }

  // Only initialize on client side
  if (typeof window === 'undefined') {
    throw new Error('Supabase client can only be used on the client side');
  }

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      'Missing Supabase environment variables: NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are required'
    );
  }

  supabaseInstance = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      storage: window.localStorage,
    },
  });

  return supabaseInstance;
}

/**
 * Authentication helper functions
 */
export const supabaseAuth = {
  /**
   * Get current session
   */
  async getSession() {
    const client = getSupabaseClient();
    const { data, error } = await client.auth.getSession();
    if (error) throw error;
    return data.session;
  },

  /**
   * Get current user
   */
  async getUser() {
    const client = getSupabaseClient();
    const { data, error } = await client.auth.getUser();
    if (error) throw error;
    return data.user;
  },

  /**
   * Sign in with email and password
   */
  async signIn(email: string, password: string) {
    const client = getSupabaseClient();
    const { data, error } = await client.auth.signInWithPassword({
      email,
      password,
    });
    if (error) throw error;
    return data;
  },

  /**
   * Sign up with email and password
   */
  async signUp(email: string, password: string, metadata?: Record<string, unknown>) {
    const client = getSupabaseClient();
    const { data, error } = await client.auth.signUp({
      email,
      password,
      options: {
        data: metadata,
      },
    });
    if (error) throw error;
    return data;
  },

  /**
   * Sign out
   */
  async signOut() {
    const client = getSupabaseClient();
    const { error } = await client.auth.signOut();
    if (error) throw error;
  },

  /**
   * Listen to auth state changes
   */
  onAuthStateChange(callback: (event: string, session: unknown) => void) {
    const client = getSupabaseClient();
    return client.auth.onAuthStateChange(callback);
  },
};

/**
 * Export the supabase client for direct access if needed
 * This will throw an error if env vars are not set or used on server side
 */
export const supabase = getSupabaseClient();
