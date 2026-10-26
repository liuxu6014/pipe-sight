export function profileFields(value = {}) {
  return { nickName: String(value.nickName || '').trim(), phonenumber: String(value.phonenumber || '').trim(), email: String(value.email || '').trim(), sex: ['0', '1', '2'].includes(value.sex) ? value.sex : '2' }
}
export function validateProfile(value) {
  const form = profileFields(value)
  if (!form.nickName || form.nickName.length > 30) return '昵称需为 1–30 个字符'
  if (form.email && (form.email.length > 50 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))) return '请输入有效邮箱地址'
  if (form.phonenumber && !/^1[3-9]\d{9}$/.test(form.phonenumber)) return '请输入有效的 11 位手机号码'
  return ''
}
export function validatePasswordChange(value = {}) {
  if (!value.oldPassword) return '请输入原密码'
  if (!value.newPassword || value.newPassword.length < 6 || value.newPassword.length > 20) return '新密码长度需为 6–20 个字符'
  if (/[<>"'|\\]/.test(value.newPassword)) return '新密码不能包含 < > " 单引号、竖线或反斜杠'
  if (value.newPassword !== value.confirmPassword) return '两次输入的新密码不一致'
  if (value.oldPassword === value.newPassword) return '新密码不能与原密码相同'
  return ''
}
