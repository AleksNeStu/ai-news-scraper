'use server'

import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { api, ApiError } from './api'

const COOKIE_NAME = 'auth_token'
const COOKIE_MAX_AGE = 60 * 60 * 24 // 1d mirror of API

export async function loginAction(_prev: unknown, formData: FormData) {
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const res = await api.post<{ user: unknown; token: string }>('/auth/login', { email, password })
    ;(await cookies()).set(COOKIE_NAME, res.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
    return { ok: true }
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message }
    return { ok: false, error: 'Login failed' }
  }
}

export async function registerAction(_prev: unknown, formData: FormData) {
  const email = String(formData.get('email') ?? '')
  const password = String(formData.get('password') ?? '')
  try {
    const res = await api.post<{ user: unknown; token: string }>('/auth/register', {
      email,
      password,
    })
    ;(await cookies()).set(COOKIE_NAME, res.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE,
    })
    return { ok: true }
  } catch (e) {
    if (e instanceof ApiError) return { ok: false, error: e.message }
    return { ok: false, error: 'Registration failed' }
  }
}

export async function logoutAction() {
  ;(await cookies()).delete(COOKIE_NAME)
  redirect('/login')
}
