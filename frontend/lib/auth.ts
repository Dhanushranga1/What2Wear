import { supabase } from './supabaseClient'

export const getUser = async () => {
  const { data: { user } } = await supabase.auth.getUser()
  return user
}

export const signOut = async () => {
  await supabase.auth.signOut()
}
