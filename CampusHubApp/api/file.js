import { upload } from '../utils/request.js'

export default {
  uploadImage(filePath) {
    return upload('/upload/image', filePath, 'image')
  },
  uploadVideo(filePath) {
    return upload('/upload/video', filePath, 'video')
  },
  uploadAvatar(filePath) {
    return upload('/upload/image', filePath, 'image')
  }
}
