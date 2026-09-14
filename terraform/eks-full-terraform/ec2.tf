resource "aws_instance" "eksctl_kubectl_server" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.eksctl_instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.eksctl_server_sg.id]
  iam_instance_profile   = data.aws_iam_instance_profile.lab_instance_profile.name

  root_block_device {
    volume_size = 8
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    cluster_name    = var.cluster_name
    aws_region      = var.aws_region
    cluster_version = var.cluster_version
  })

  depends_on = [aws_eks_cluster.this]

  tags = {
    Name = var.eksctl_instance_name
  }
}
