<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const router = useRouter()
const auth = useAuthStore()
const isRegister = ref(false)
const form = reactive({
  phone: '', email: '', first_name: '', last_name: '',
  password: '', password_confirm: '',
})

watch(isRegister, () => {
  auth.clearError()
  Object.assign(form, { phone: '', email: '', first_name: '', last_name: '', password: '', password_confirm: '' })
})

async function handleSubmit() {
  if (isRegister.value) await auth.register(form)
  else await auth.login(form.phone, form.password)

  if (auth.isAuthenticated) {
    router.push('/')
  }
}
</script>

<template>
  <div class="auth-screen">
    <div class="auth-card">
      <h2>{{ isRegister ? 'Регистрация' : 'Вход' }}</h2>
      <div v-if="auth.error" class="error-msg">{{ auth.error }}</div>
      <form @submit.prevent="handleSubmit">
        <input v-model="form.phone" class="form-input" placeholder="Телефон (+79991234567)" required />
        <template v-if="isRegister">
          <input v-model="form.email" class="form-input" placeholder="Email" type="email" required />
          <input v-model="form.first_name" class="form-input" placeholder="Имя" required />
          <input v-model="form.last_name" class="form-input" placeholder="Фамилия" required />
        </template>
        <input v-model="form.password" class="form-input" type="password" placeholder="Пароль" required />
        <input v-if="isRegister" v-model="form.password_confirm" class="form-input" type="password" placeholder="Подтвердите пароль" required />
        <button class="btn-primary" :disabled="auth.isLoading">
          {{ auth.isLoading ? '...' : isRegister ? 'Зарегистрироваться' : 'Войти' }}
        </button>
      </form>
      <div class="auth-toggle" @click="isRegister = !isRegister">
        {{ isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться' }}
      </div>
    </div>
  </div>
</template>