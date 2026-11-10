const copyAccount = document.querySelector('[data-copy-fundraising-account]');
if (copyAccount) {
  const account = document.getElementById('fundraising-account-number');
  const result = document.querySelector('.fundraising-copy-result');
  copyAccount.hidden = false;
  copyAccount.addEventListener('click', async () => {
    copyAccount.disabled = true;
    result.textContent = '복사 중입니다.';
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(account.textContent.trim());
      result.textContent = '계좌번호를 복사했습니다.';
    } catch {
      result.textContent = '계좌번호를 복사하지 못했습니다. 표시된 계좌번호를 직접 선택해 복사해 주세요.';
    } finally {
      copyAccount.disabled = false;
    }
  });
}
