/** Provider values, not optimistic UI booleans. Type/status are Android Telephony.Sms values. */
export function smsState(type, status) {
  if (type === 1) return "Alındı";
  if (type === 3) return "Taslak · gönderilmedi";
  if (type === 4 || type === 6)
    return "Gönderim bekleniyor · henüz doğrulanmadı";
  if (type === 5)
    return "Gönderilemedi / kısmi başarısızlık · otomatik tekrar yok";
  if (type !== 2) return "Bilinmeyen sistem durumu";
  if (status === 0) return "Şebekeye verildi · teslim raporu alındı";
  if (status >= 64) return "Şebekeye verildi · teslim başarısız";
  return "Şebekeye verildi · teslim doğrulanmadı";
}
