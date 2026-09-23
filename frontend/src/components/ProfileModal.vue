<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { useAuthStore } from '../stores/auth'

const props = defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()

const auth = useAuthStore()

const form = reactive({ first_name: '', last_name: '', email: '', phone: '' })
const error = ref('')
const isSaving = ref(false)

function fillFromProfile() {
  const u = auth.user
  form.first_name = u?.first_name || ''
  form.last_name = u?.last_name || ''
  form.email = u?.email || ''
  form.phone = u?.phone || ''
  error.value = ''
}

// Данные подставляем при каждом открытии: профиль мог обновиться из другого места
watch(() => props.isOpen, (open) => {
  if (open) fillFromProfile()
})

// Esc закрывает модалку; ChatWindow по наличию .modal-overlay в этот момент чат не трогает
onKeyStroke('Escape', () => {
  if (props.isOpen) emit('close')
})

async function save() {
  if (isSaving.value) return
  error.value = ''
  const phone = form.phone.trim()
  if (!phone) {
    error.value = 'Телефон не может быть пустым'
    return
  }
  isSaving.value = true
  const ok = await auth.updateProfile({
    first_name: form.first_name.trim(),
    last_name: form.last_name.trim(),
    email: form.email.trim(),
    phone,
  })
  isSaving.value = false
  if (ok) emit('close')
  else error.value = auth.error
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="modal-overlay" @click.self="emit('close')">
      <div class="modal profile-modal">
        <h3>Профиль</h3>
        <div v-if="error" class="error-msg">{{ error }}</div>

        <label class="form-label" for="profile-first-name">Имя</label>
        <input
          id="profile-first-name"
          v-model="form.first_name"
          class="form-input"
          type="text"
          maxlength="150"
          autocomplete="given-name"
        />

        <label class="form-label" for="profile-last-name">Фамилия</label>
        <input
          id="profile-last-name"
          v-model="form.last_name"
          class="form-input"
          type="text"
          maxlength="150"
          autocomplete="family-name"
        />

        <label class="form-label" for="profile-email">Email</label>
        <input
          id="profile-email"
          v-model="form.email"
          class="form-input"
          type="email"
          maxlength="254"
          autocomplete="email"
          placeholder="Необязательно"
        />

        <label class="form-label" for="profile-phone">Телефон</label>
        <input
          id="profile-phone"
          v-model="form.phone"
          class="form-input"
          type="tel"
          maxlength="20"
          autocomplete="tel"
        />
        <div class="form-hint">Телефон — это логин: входить после смены нужно новым номером.</div>

        <button class="btn-primary" :disabled="isSaving" @click="save">
          {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
        </button>
        <button class="btn-secondary" @click="emit('close')">Отмена</button>
      </div>
    </div>
  </Teleport>
</template>
