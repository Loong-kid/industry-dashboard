/* 테마: 차트 글자도 화면과 같은 Pretendard로 그린다. 색은 app.js가 CSS 토큰에서 읽는다. */
"use strict";
if (window.Chart) {
  Chart.defaults.font.family = '"Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif';
}
