import assert from 'node:assert/strict'
import test from 'node:test'
import {
  PROFILE_AVATAR_CHANGED_EVENT,
  migrateLegacyProfileAvatar,
  profileAvatarStorageKey,
} from '../lib/auth.ts'

const API_AVATAR_URL = '/api/auth/avatar'

function testUser(avatarUrl = null) {
  return {
    id: 42,
    name: 'Usuário de teste',
    email: 'avatar@example.com',
    plan: 'fiel',
    is_active: true,
    avatar_url: avatarUrl,
  }
}

async function withBrowserEnvironment(entries, fetchImplementation, callback) {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  const previousLocalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  const previousFetch = globalThis.fetch
  const previousCustomEvent = Object.getOwnPropertyDescriptor(globalThis, 'CustomEvent')
  const values = new Map(entries)
  const events = []

  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem(key) {
        return values.has(key) ? values.get(key) : null
      },
      setItem(key, value) {
        values.set(key, String(value))
      },
      removeItem(key) {
        values.delete(key)
      },
    },
  })
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      location: { origin: 'https://verafidei.oialfred.com' },
      dispatchEvent(event) {
        events.push(event)
        return true
      },
    },
  })
  Object.defineProperty(globalThis, 'CustomEvent', {
    configurable: true,
    value: class CustomEvent extends Event {
      constructor(type, init = {}) {
        super(type)
        this.detail = init.detail
      }
    },
  })
  globalThis.fetch = fetchImplementation

  try {
    return await callback({ values, events })
  } finally {
    if (previousWindow) Object.defineProperty(globalThis, 'window', previousWindow)
    else delete globalThis.window
    if (previousLocalStorage) Object.defineProperty(globalThis, 'localStorage', previousLocalStorage)
    else delete globalThis.localStorage
    globalThis.fetch = previousFetch
    if (previousCustomEvent) Object.defineProperty(globalThis, 'CustomEvent', previousCustomEvent)
    else delete globalThis.CustomEvent
  }
}

test('migra data URI sem fazer fetch nela e remove a chave somente após o upload', async () => {
  const user = testUser()
  const key = profileAvatarStorageKey(user.id)
  const legacyAvatar = 'data:image/png;base64,iVBORw0KGgo='
  const requests = []

  await withBrowserEnvironment([[key, legacyAvatar]], async (url, init) => {
    requests.push({ url: String(url), init })
    assert.equal(String(url).startsWith('data:'), false)
    return new Response(JSON.stringify({ avatar_url: '/api/auth/avatar?v=123' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }, async ({ values, events }) => {
    const migrated = await migrateLegacyProfileAvatar(user)

    assert.equal(migrated, 'https://verafidei.oialfred.com/api/auth/avatar?v=123')
    assert.equal(requests.length, 1)
    assert.equal(requests[0].url, API_AVATAR_URL)
    assert.equal(requests[0].init.method, 'PUT')
    assert.equal(requests[0].init.body.type, 'image/png')
    assert.equal(values.has(key), false)
    assert.equal(events.length, 1)
    assert.equal(events[0].type, PROFILE_AVATAR_CHANGED_EVENT)
    assert.equal(events[0].detail.userId, user.id)
    assert.equal(events[0].detail.avatar, migrated)
  })
})

test('mantém o avatar local e sua chave quando o upload falha', async () => {
  const user = testUser()
  const key = profileAvatarStorageKey(user.id)
  const legacyAvatar = 'data:image/png;base64,iVBORw0KGgo='

  await withBrowserEnvironment([[key, legacyAvatar]], async () => {
    return new Response(JSON.stringify({ detail: 'Falha simulada' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }, async ({ values, events }) => {
    const migrated = await migrateLegacyProfileAvatar(user)

    assert.equal(migrated, legacyAvatar)
    assert.equal(values.get(key), legacyAvatar)
    assert.equal(events.length, 0)
  })
})

test('prefere o avatar já salvo no servidor e limpa o legado sem novo upload', async () => {
  const serverAvatar = 'https://verafidei.oialfred.com/api/auth/avatar?v=456'
  const user = testUser(serverAvatar)
  const key = profileAvatarStorageKey(user.id)

  await withBrowserEnvironment([[key, 'data:image/png;base64,iVBORw0KGgo=']], async () => {
    throw new Error('fetch não deveria ser chamado')
  }, async ({ values }) => {
    const migrated = await migrateLegacyProfileAvatar(user)

    assert.equal(migrated, serverAvatar)
    assert.equal(values.has(key), false)
  })
})

for (const legacyMime of ['image/jpg', 'image/pjpeg']) {
  test(`normaliza MIME legado ${legacyMime} para image/jpeg`, async () => {
    const user = testUser()
    const key = profileAvatarStorageKey(user.id)
    const legacyAvatar = `data:${legacyMime};base64,/9j/AA==`
    let uploadedBlob

    await withBrowserEnvironment([[key, legacyAvatar]], async (_url, init) => {
      uploadedBlob = init.body
      return new Response(JSON.stringify({ avatar_url: '/api/auth/avatar?v=789' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }, async ({ values }) => {
      await migrateLegacyProfileAvatar(user)

      assert.equal(uploadedBlob.type, 'image/jpeg')
      assert.equal(values.has(key), false)
    })
  })
}
