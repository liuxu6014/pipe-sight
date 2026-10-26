// Server revocation can fail for stale tokens or an unavailable server.
// Neither case may keep a user trapped in an authenticated local UI.
export async function endSession(revoke, clear) {
  try {
    await revoke()
    return true
  } catch {
    return false
  } finally {
    await clear()
  }
}
